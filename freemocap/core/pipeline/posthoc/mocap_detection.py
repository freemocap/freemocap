"""Lossless multiframe coordination across video threads and shared inference."""

from collections.abc import Iterator
from concurrent.futures import CancelledError, Future, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import TypeVar

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoBoardSelector

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.inference_service import InferenceService, InferenceRegistration, InferenceRequest, InferenceMode
from freemocap.core.pipeline.posthoc.mocap_video_node import MocapVideoNode, VideoWorkerConfig, ReadFrame, AnnotateFrame, FinishVideo
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper, VideoMetadata
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.tracker_factory import tracker_session_requests

Result = TypeVar("Result")


@dataclass(frozen=True)
class MocapDetectionRequest:
    recording_path: Path
    config: PosthocMocapPipelineConfig
    ipc: PipelineIPC
    progress: Queue[PipelineProgressMessage]
    registry: WorkerRegistry
    inference_service: InferenceService
    video_nodes: list[MocapVideoNode]


@dataclass(frozen=True)
class MocapDetectionFrame:
    frame_number: int
    frame_count: int
    observations: dict[str, Observation]
    selected_board: CharucoBoardDefinition | None
    video_metadata: dict[str, VideoMetadata]


def _wait(*, future: Future[Result], request: MocapDetectionRequest, nodes: list[MocapVideoNode]) -> Result:
    while True:
        try:
            return future.result(timeout=0.05)
        except CancelledError:
            for node in nodes:
                if node.failure is not None:
                    raise node.failure
            raise
        except TimeoutError:
            if future.done():
                raise
            for node in nodes:
                if node.failure is not None:
                    raise node.failure
                if not node.worker.is_alive():
                    raise RuntimeError(f"Video worker exited before completing requested work: {node.config.camera_id}")
            if not request.ipc.should_continue:
                raise CancelledError("Mocap pipeline stopped")


def detect_mocap_recording(request: MocapDetectionRequest) -> Iterator[MocapDetectionFrame]:
    group = VideoGroupHelper.from_recording_path(recording_path=str(request.recording_path))
    try:
        metadata = group.video_metadata_by_id
        frame_count = group.frame_count
    finally:
        group.close()
    nodes = request.video_nodes
    client = request.inference_service.register(InferenceRegistration(
        pipeline_id=request.ipc.pipeline_id, mode=InferenceMode.POSTHOC,
        tracker_config=request.config.tracker_config,
        sessions=tracker_session_requests(config=request.config.tracker_config, batch_size=len(metadata), execution_provider=None),
        shutdown_flag=request.ipc.pipeline_shutdown_flag,
    ))
    completed = False
    try:
        for camera_id, video in metadata.items():
            node = MocapVideoNode(config=VideoWorkerConfig(camera_id=camera_id, video=video,
                recording_path=request.recording_path, tracker_config=request.config.tracker_config,
                ipc=request.ipc, progress=request.progress), registry=request.registry)
            node.worker.start()
            nodes.append(node)
        selected = request.config.charuco_board if request.config.charuco_tracking_enabled and request.config.board_mode == CharucoBoardMode.EXPLICIT else None
        selector = CharucoBoardSelector() if request.config.charuco_tracking_enabled and selected is None else None
        reads = {node.config.camera_id: ReadFrame(number=0) for node in nodes}
        for node in nodes:
            node.commands.put_nowait(reads[node.config.camera_id])
        for number in range(frame_count):
            if not request.ipc.should_continue:
                raise CancelledError("Mocap pipeline stopped")
            images = {camera: _wait(future=command.result, request=request, nodes=nodes) for camera, command in reads.items()}
            inference = client.submit(InferenceRequest(frame_number=number, images=images))
            # Decode one multiframe ahead while inference owns the current images.
            if number + 1 < frame_count:
                reads = {node.config.camera_id: ReadFrame(number=number + 1) for node in nodes}
                for node in nodes:
                    node.commands.put_nowait(reads[node.config.camera_id])
            if selector is not None and selected is None:
                detected = selector.search_frame(frame_number=number, images=images.values())
                if detected is not None:
                    selected = detected.model_copy(update={"square_length_mm": request.config.charuco_board.square_length_mm})
            observations = _wait(future=inference, request=request, nodes=nodes)
            annotations = {camera: AnnotateFrame(image=images[camera], observation=observation, board=selected)
                           for camera, observation in observations.items()}
            for node in nodes:
                node.commands.put_nowait(annotations[node.config.camera_id])
            merged = {camera: _wait(future=command.result, request=request, nodes=nodes) for camera, command in annotations.items()}
            yield MocapDetectionFrame(frame_number=number, frame_count=frame_count,
                observations=merged, selected_board=selected, video_metadata=metadata)
        for publish in (False, True):
            finishes = [FinishVideo(publish=publish) for node in nodes]
            for node, command in zip(nodes, finishes, strict=True):
                node.commands.put_nowait(command)
            # Finished video workers may exit while their siblings finalize output.
            for command in finishes:
                while True:
                    try:
                        command.result.result(timeout=0.05)
                        break
                    except TimeoutError:
                        if command.result.done():
                            raise
                        for node in nodes:
                            if node.failure is not None:
                                raise node.failure
                        if not request.ipc.should_continue:
                            raise CancelledError("Mocap pipeline stopped")
        completed = True
    finally:
        client.close()
        if not completed:
            request.ipc.shutdown_pipeline()
        for node in nodes:
            node.worker.mark_stopping()
        for node in nodes:
            node.worker.join(timeout=10.0)
        alive = [node.config.camera_id for node in nodes if node.worker.is_alive()]
        if alive:
            raise RuntimeError(f"Video threads did not finish shutdown: {alive}")
