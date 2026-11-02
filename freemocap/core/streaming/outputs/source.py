"""Read numerical stream samples independently of WebSocket connections."""
from __future__ import annotations

from skellycam.core.camera.config.image_rotation_types import RotationTypes

from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.message_model import CalibratedCamera, CameraCalibrationMatch, CameraRotation
from freemocap.core.streaming.outputs.contracts import OutputSample, SourceBatch
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage


_ROTATIONS = {
    RotationTypes.CLOCKWISE_90: CameraRotation.CLOCKWISE_90,
    RotationTypes.ROTATE_180: CameraRotation.ROTATE_180,
    RotationTypes.COUNTERCLOCKWISE_90: CameraRotation.COUNTERCLOCKWISE_90,
}


def describe_cameras(bindings, configs) -> tuple[CalibratedCamera, ...]:
    """Project the aggregator's existing calibration bindings using live image geometry."""
    cameras = []
    for binding in bindings:
        config = configs.get(binding.live_camera_id)
        if config is None:
            continue
        args = dict(camera_id=binding.live_camera_id, camera_index=config.camera_index,
                    rotation=_ROTATIONS.get(config.rotation, CameraRotation.NONE),
                    image_size=(config.width, config.height))
        if binding.camera_model is None:
            cameras.append(CalibratedCamera.unmatched(**args))
        else:
            cameras.append(CalibratedCamera.from_camera_model(binding.camera_model,
                **args, match_kind=CameraCalibrationMatch(binding.match_kind),
                calibration_camera_id=binding.calibration_camera_id))
    return tuple(cameras)


class RuntimeOutputSource:
    def __init__(self, app):
        self.app = app
        self.cursors: dict[str, int] = {}
        self.owners: dict[str, int] = {}
        self.compositions: dict = {}

    def source_ids(self) -> tuple[str, ...]:
        manager = self.app.realtime_pipeline_manager
        with manager.lock:
            return tuple(key for key, pipeline in manager.pipelines.items() if pipeline.alive)

    def poll(self) -> SourceBatch:
        manager = self.app.realtime_pipeline_manager
        with manager.lock:
            pipelines = tuple((key, pipe) for key, pipe in manager.pipelines.items() if pipe.alive)
        alive = tuple(key for key, _ in pipelines)
        for key in tuple(self.owners):
            if key not in alive:
                self.owners.pop(key, None)
                self.cursors.pop(key, None)
                self.compositions.pop(key, None)
        samples = []
        errors = {}
        for key, pipeline in pipelines:
            try:
                if self.owners.get(key) != id(pipeline):
                    self.owners[key] = id(pipeline)
                    self.cursors.pop(key, None)
                    self.compositions.pop(key, None)
                # Runs on the server loop, as do existing websocket readers. Each
                # reader has its own cursor into the pipeline's retained result.
                output = pipeline.get_latest_aggregator_output(self.cursors.get(key, -1))
                if output is None:
                    continue
                camera_times = tuple(sorted((node.camera_id, node.capture_timestamp_ns)
                    for node in output.camera_node_outputs.values()
                    if isinstance(node, CameraNodeOutputMessage)))
                if (not camera_times or any(value is None for _, value in camera_times)
                    or {name for name, _ in camera_times} != set(pipeline.camera_ids)):
                    raise ValueError("Original acquisition nanoseconds required for every source camera")
                # Same multi-camera mean convention as SkellyCam recording CSVs;
                # original integer camera timestamps remain attached separately.
                whole_ns, remainder = divmod(sum(value for _, value in camera_times), len(camera_times))
                source_ns = whole_ns if remainder == 0 else whole_ns + remainder / len(camera_times)
                config = output.pipeline_config
                cameras = describe_cameras(output.calibration_bindings, pipeline.camera_configs)
                signature = (config.camera_node_config.model_dump_json(),
                             config.aggregator_config.anchor_segment_name, cameras)
                cached = self.compositions.get(key)
                if cached is None or cached[0] != signature:
                    context = StreamContext(
                        skeletons=build_tracked_skeletons(camera_node_config=config.camera_node_config,
                            anchor_segment_name=config.aggregator_config.anchor_segment_name),
                        camera_ids=tuple(pipeline.camera_ids), calibrated_cameras=cameras,
                        detector_type=config.camera_node_config.detector_type, pipeline_live=True,
                        live_image_sizes={name: (cfg.width, cfg.height)
                                          for name, cfg in pipeline.camera_configs.items()})
                    cached = (signature, compose_messages(context))
                    self.compositions[key] = cached
                frame = cached[1].compose_frame_message(FrameContext(frame_number=output.frame_number,
                    timestamp=float(source_ns), aggregator_output=output))
                samples.append(OutputSample(frame, key, source_ns, camera_times))
                self.cursors[key] = output.frame_number
            except Exception as error:
                errors[key] = f"{type(error).__name__}: {error}"
        return SourceBatch(tuple(samples), alive, errors)
