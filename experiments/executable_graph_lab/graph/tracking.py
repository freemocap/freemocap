"""Real 2D tracking integration; no call to the old posthoc coordinator.

CLI writes a new isolated result directory. Existing recordings are read-only.
The application entry point is intentionally not switched until all task graph
variants have adapters. This is a validation entry point for that replacement.
"""
import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Full, Queue
from time import perf_counter, sleep

import numpy as np
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader
from skellytracker.core import Tracker
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.sessions.model_registry import ModelSource, DEFAULT_CACHE_DIR
from skellytracker.core.sessions.onnx_session import OnnxSession, OnnxSessionConfig

from experiments.executable_graph_lab.graph.runtime import Binding, Executor, Node, Window, compile_plan
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper, VideoMetadata
from freemocap.core.reconstruction.recording_timing import RecordingGroupTiming
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.tracker_factory import tracker_session_requests


@dataclass(frozen=True)
class RecordingContext:
    source: Path
    videos: dict[str, VideoMetadata]
    frames: int


@dataclass(frozen=True)
class SessionDescriptor:
    providers: dict[str, tuple[str, ...]]
    cameras: tuple[str, ...]
    device_id: int


@dataclass(frozen=True)
class Frame:
    camera: str
    number: int
    timestamp_s: float
    image: np.ndarray

    def __post_init__(self):
        if self.image.dtype != np.uint8 or self.image.ndim != 3 or self.image.shape[2] != 3:
            raise ValueError('Expected BGR uint8 H×W×3 image')
        if self.number < 0 or not np.isfinite(self.timestamp_s): raise ValueError('Invalid frame identity')
        self.image.setflags(write=False)

    @property
    def pixel_bytes(self): return self.image.nbytes


@dataclass(frozen=True)
class Observations:
    number: int
    cameras: dict[str, Observation]


@dataclass(frozen=True)
class Publication:
    path: str
    frames: int
    cameras: tuple[str, ...]


class SnapshotWriter:
    """One bounded pending snapshot; diagnostic disk I/O never gates dispatch."""
    def __init__(self, output):
        self.output, self.queue = output, Queue(maxsize=1)
        self.pool = ThreadPoolExecutor(max_workers=1,thread_name_prefix='graph-snapshots')
        self.worker = self.pool.submit(self.write)

    def submit(self, snapshot):
        try: self.queue.put_nowait(snapshot)
        except Full:
            try: self.queue.get_nowait()
            except Empty: pass
            self.queue.put_nowait(snapshot)

    def write(self):
        error = None
        while True:
            snapshot = self.queue.get()
            if snapshot is None: break
            if error is not None: continue
            try:
                tmp = self.output / 'snapshot.tmp'
                tmp.write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
                for attempt in range(6):
                    try:
                        tmp.replace(self.output / 'snapshot.json')
                        break
                    except PermissionError:
                        if attempt==5: raise
                        sleep(.02*(attempt+1))
            except Exception as exc: error = exc
        if error: raise error

    def close(self):
        self.queue.put(None)
        try: self.worker.result()
        finally: self.pool.shutdown(wait=True)


def tracking_plan(context: RecordingContext, destination: Path, prefetch: int = 2):
    def b(port, source, payload, rule='broadcast'): return Binding(port, source, payload, rule)
    return compile_plan((
        Node('recording', 'Recording context', 'recording', 'cpu', RecordingContext),
        Node('config', 'Configure RTMPose', 'recording', 'cpu', PosthocMocapPipelineConfig),
        Node('timing', 'Resolve recording timing', 'recording', 'cpu', RecordingGroupTiming,
             (b('recording','recording',RecordingContext),)),
        Node('session', 'Open CUDA inference session', 'recording', 'gpu', SessionDescriptor,
             (b('recording','recording',RecordingContext), b('config','config',PosthocMocapPipelineConfig)),
             lifetime_users=('session','track')),
        Node('decode', 'Load video frames', 'camera_frame', 'io', Frame,
             (b('recording','recording',RecordingContext), b('timing','timing',RecordingGroupTiming)),
             ordered=True, io_role='read', io_files=tuple(str(v.file_path) for v in context.videos.values()),
             window=Window('track',prefetch),lifetime_users=('decode',), work_unit='camera frames',
             description='Read synchronized videos and convert compressed frames into BGR pixel arrays in memory. Each camera loads in order; different cameras can load concurrently. Images are released after tracking consumes them.'),
        Node('track', 'Track poses with RTMPose', 'frame', 'gpu', Observations,
             (b('images','decode',Frame,'all_sources'), b('session','session',SessionDescriptor)), ordered=True, work_unit='camera batches',
             description='Run RTMPose on the GPU for one synchronized frame from every camera per call. A batch waits for those camera images and the model session, then produces 2D observations for every camera.'),
        Node('publish', 'Save 2D tracking results', 'recording', 'cpu', Publication,
             (b('observations','track',Observations,'sealed'), b('timing','timing',RecordingGroupTiming),
              b('recording','recording',RecordingContext), b('config','config',PosthocMocapPipelineConfig)),
             io_role='write', io_files=(str(destination / f'{destination.name}_data.parquet'),), work_unit='result files',
             description='Collect all tracked frames and save 2D observations, bounding boxes, and timestamps to a new Parquet file. The source videos stay unchanged. This graph does not yet generate annotated videos or 3D results.'),
    ), tuple(context.videos), context.frames)


class TrackingAdapters:
    def __init__(self, context, config, destination):
        self.context, self.config, self.destination = context, config, destination
        self.executor = None
        self.readers, self.states = {}, {}
        self.tracker = None
        self.provider_report = {}

    def handlers(self):
        return dict(recording=lambda w,i:self.context, config=lambda w,i:self.config,
                    timing=self.timing, session=self.session, decode=self.decode, track=self.track, publish=self.publish)

    def timing(self, work, inputs):
        context = inputs['recording'][0]
        return RecordingGroupTiming.resolve(recording_folder=context.source, videos=context.videos,
                                            frame_numbers=tuple(range(context.frames)))

    def session(self, work, inputs):
        context, config = inputs['recording'][0], inputs['config'][0]
        requests = tracker_session_requests(config=config.tracker_config, batch_size=len(context.videos), execution_provider='cuda')
        if len(requests)!=1 or requests[0].config.backend!='onnx': raise ValueError('2D integration requires ONNX RTMPose only')
        # Never download a model implicitly or modify the user's cached weights.
        local_models = []
        model_dir = self.destination / '.models'
        model_dir.mkdir()
        for spec in requests[0].config.models:
            if not spec.source.url: raise ValueError('Integration requires an already cached URL model')
            cached = DEFAULT_CACHE_DIR / spec.source.url.rsplit('/',1)[-1].replace('.zip','.onnx')
            if not cached.is_file(): raise FileNotFoundError(f'Cached model required: {cached}')
            local = model_dir / cached.name
            shutil.copyfile(cached, local)
            local_models.append(replace(spec, source=ModelSource(local_path=str(local))))
        session = OnnxSession.create(OnnxSessionConfig(batch_size=len(context.videos), models=local_models, execution_provider='cuda'))
        self.executor.own('gpu', session.close,owner=work)
        providers = {spec.name: tuple(session.get_session(spec.name).get_providers()) for spec in local_models}
        if any(not values or values[0]!='CUDAExecutionProvider' for values in providers.values()):
            raise RuntimeError(f'CUDA provider requirement failed: {providers}')
        self.provider_report = dict(models=providers, device_id=session.device_id, batch_size=len(context.videos))
        self.tracker = Tracker.create_with_shared_sessions(config=config.tracker_config, sessions={'onnx':session})
        self.executor.own('gpu', self.tracker.close,owner=work)
        return SessionDescriptor(providers, tuple(context.videos), session.device_id)

    def decode(self, work, inputs):
        context, timing = inputs['recording'][0], inputs['timing'][0]
        if work.camera not in self.readers:
            reader = SequentialVideoReader(path=context.videos[work.camera].file_path)
            self.readers[work.camera] = reader
            self.executor.own('io', reader.close,owner=work)
        image = self.readers[work.camera].read_bgr(frame_number=work.frame)
        if image is None: raise ValueError(f'Unexpected video EOF: {work.id}')
        return Frame(work.camera, work.frame, timing.synchronized.timestamps_s[work.frame], image)

    def track(self, work, inputs):
        images, descriptor = inputs['images'], inputs['session'][0]
        if (tuple(f.camera for f in images)!=descriptor.cameras or any(f.number!=work.frame for f in images)
                or len({f.timestamp_s for f in images})!=1): raise ValueError('Unsynchronized camera batch')
        observations, self.states = self.tracker.process_batch(
            images={f.camera:f.image for f in images}, frame_number=work.frame,
            states=self.states, timestamp_ms=round(images[0].timestamp_s*1000))
        if set(observations)!=set(descriptor.cameras): raise ValueError('Missing camera observation')
        for f in images:
            obs = observations[f.camera]
            if obs.frame_number!=f.number or obs.image_size!=f.image.shape[:2]:
                raise ValueError('Observation identity or image dimensions changed')
        return Observations(work.frame, observations)

    def publish(self, work, inputs):
        from freemocap.core.recording.result_processing.observation_inputs import (
            ObservationRecordingRequest, ObservationGroup, TrackerRecordingDefinition, DetectorRecordingDefinition, camera_group_name)
        from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
        from freemocap.core.recording.result_processing.provenance import ProvenanceContext
        context, config, timing = inputs['recording'][0], inputs['config'][0], inputs['timing'][0]
        frames = [item.cameras for item in inputs['observations']]
        if [item.number for item in inputs['observations']]!=list(range(context.frames)):
            raise ValueError('Observation checkpoint is incomplete')
        request = ObservationRecordingRequest(
            reprojection=None, filtering=None, models=(), reconstructions=(), spatial_series=(), camera_geometry=(),
            recording=RecordingInfo(recording_name=self.destination.name, recording_directory=str(self.destination.parent)),
            group=ObservationGroup(name=camera_group_name(context.videos), frames=frames, videos=context.videos),
            tracker=TrackerRecordingDefinition(name=f'keypoint_model:{config.rtmpose_model_name}',
                configuration=config.model_dump(mode='json'), point_names=tuple(dict.fromkeys(
                    name for frame in frames for obs in frame.values() for name in obs.to_keypoints().names))),
            detector=DetectorRecordingDefinition(name='object_detector:yolox-m', configuration=config.model_dump(mode='json'),
                box_names=tuple(dict.fromkeys(stage.name for frame in frames for obs in frame.values() for stage in obs.stages.values()))),
            resolved_timing=timing, provenance_context=ProvenanceContext.create(),
            provenance_defaults=PosthocMocapPipelineConfig().model_dump(mode='json'))
        publish_posthoc_observations(request)
        path = self.destination / f'{self.destination.name}_data.parquet'
        return Publication(str(path), len(frames), tuple(context.videos))


def inspect_recording(source: Path, video_subfolder: str, frames: int | None = None):
    group = VideoGroupHelper.from_recording_path(str(source), video_subfolder_name=video_subfolder)
    try:
        if frames is not None and (type(frames) is not int or frames < 1):
            raise ValueError('Explicit frame limit must be a positive integer')
        count = group.frame_count if frames is None else min(frames, group.frame_count)
        videos = {camera:video.model_copy(update={'end_frame':count}) for camera,video in group.video_metadata_by_id.items()}
        return RecordingContext(source, videos, count)
    finally: group.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('--output',type=Path,required=True,help='New output root; must not exist')
    parser.add_argument('--video-subfolder',default='synchronized_videos')
    parser.add_argument('--frames',type=int,default=None,help='Optional explicit frame limit; defaults to the full recording')
    parser.add_argument('--prefetch',type=int,default=2)
    args = parser.parse_args()
    if args.frames is not None and args.frames < 1: parser.error('--frames must be positive when supplied')
    if not 1<=args.prefetch<=8: parser.error('--prefetch must be between 1 and 8')
    source, output = args.recording.resolve(strict=True), args.output.resolve()
    if source==output or source in output.parents: parser.error('Output must be outside the source recording')
    output.mkdir(parents=True,exist_ok=False)
    destination = output / source.name
    destination.mkdir()
    context = inspect_recording(source,args.video_subfolder,args.frames)
    config = PosthocMocapPipelineConfig(detector_type='rtmpose',charuco_tracking_enabled=False,
                                      video_fps=next(iter(context.videos.values())).fps)
    plan = tracking_plan(context,destination,args.prefetch)
    adapters = TrackingAdapters(context,config,destination)
    reporter = SnapshotWriter(output)
    executor = Executor(plan,adapters.handlers(),dict(cpu=1,io=len(context.videos),gpu=1),observer=reporter.submit)
    adapters.executor = executor
    (output/'graph.json').write_text(json.dumps(plan.describe(),indent=2),encoding='utf-8')
    started = perf_counter()
    try:
        executor.run()
    finally:
        reporter.close()
        summary = executor.snapshot() | dict(providers=adapters.provider_report, source=str(source),
            frames=context.frames, cameras=len(context.videos), elapsed_including_cleanup_s=perf_counter()-started)
        track = summary['timings']['track']
        if track['calls']:
            span = track['last_finished_s'] - track['first_started_s']
            summary['tracking_batches_per_second'] = track['calls']/span
            summary['mean_tracking_call_ms'] = 1000*track['seconds']/track['calls']
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k not in ('states','events')},indent=2))


if __name__=='__main__': main()
