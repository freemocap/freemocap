"""
CharucoRecorderNode: persists Charuco observations from realtime CameraNodes
during calibration recording windows, so posthoc calibration can skip
redundant OpenCV detection.
"""
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.types.type_overloads import CameraIdString
from skellytracker.trackers.charuco_tracker.charuco_board_definition import CharucoBoardDefinition
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.types.type_overloads import TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    CalibrationRecordingStateMessage,
    CalibrationRecordingStateTopic,
    CameraNodeOutputMessage,
    CameraNodeOutputTopic,
)

logger = logging.getLogger(__name__)

CACHE_FILENAME = "charuco_observations_realtime.pkl"
OUTPUT_DATA_DIR = "output_data"


@dataclass
class CharucoRecorderNode(SourceNode):
    """Buffers CharucoObservations during calibration recordings.

    Subscribes to CameraNodeOutputTopic (for observations) and
    CalibrationRecordingStateTopic (for start/stop signals).

    On recording stop, pickles the full buffer to
    ``{recording_path}/output_data/charuco_observations_realtime.pkl``.
    """

    camera_ids: list[CameraIdString] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        camera_ids: list[CameraIdString],
        board_config: CharucoBoardDefinition,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
        worker_registry: WorkerRegistry,
    ) -> "CharucoRecorderNode":
        camera_node_output_sub = pubsub.get_subscription(CameraNodeOutputTopic)
        recording_state_sub = pubsub.get_subscription(CalibrationRecordingStateTopic)

        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name="CharucoRecorderNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_ids=camera_ids,
                board_config=board_config,
                camera_node_output_sub=camera_node_output_sub,
                recording_state_sub=recording_state_sub,
                ipc=ipc,
                shutdown_self_flag=None,
            ),
        )
        return cls(
            camera_ids=camera_ids,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        camera_ids: list[CameraIdString],
        board_config: CharucoBoardDefinition,
        camera_node_output_sub: TopicSubscriptionQueue,
        recording_state_sub: TopicSubscriptionQueue,
        ipc: PipelineIPC,
        shutdown_self_flag: Synchronized | None,
    ) -> None:
        from queue import Empty

        logger.info("CharucoRecorderNode started — waiting for calibration recording signal")

        # Observations keyed by their TRUE connection frame number
        # (CameraNodeOutputMessage.frame_number == frame_metadata.frame_number),
        # NOT by arrival order. This is the same identifier skellycam records as
        # `connection_frame_number` in the per-camera timestamps CSV, so posthoc
        # calibration can map each recorded video frame back to its observation
        # even though the realtime pipeline drops frames it can't keep up with.
        buffer: dict[CameraIdString, dict[int, CharucoObservation]] = {
            cid: {} for cid in camera_ids
        }
        recording_info = None
        is_recording = False

        try:
            while ipc.should_continue:
                if shutdown_self_flag is not None and shutdown_self_flag.value:
                    break

                # Drain recording state messages (first, to toggle recording)
                while ipc.should_continue:
                    try:
                        msg = recording_state_sub.get_nowait()
                        if isinstance(msg, CalibrationRecordingStateMessage):
                            if msg.is_active and not is_recording:
                                is_recording = True
                                recording_info = msg.recording_info
                                buffer = {cid: {} for cid in camera_ids}
                                logger.info(
                                    f"Calibration recording started: "
                                    f"{recording_info.recording_name if recording_info else 'unknown'}"
                                )
                            elif not msg.is_active and is_recording:
                                is_recording = False
                                logger.info(
                                    f"Calibration recording stopped — "
                                    f"flushing {sum(len(v) for v in buffer.values())} observations"
                                )
                                _flush_buffer(
                                    buffer=buffer,
                                    recording_info=recording_info,
                                    board_config=board_config,
                                )
                    except Empty:
                        break
                    except (OSError, EOFError):
                        # Queue closed during shutdown on Windows
                        break

                # Drain camera node output messages (only when recording)
                while ipc.should_continue:
                    try:
                        msg = camera_node_output_sub.get_nowait()
                        if (
                            is_recording
                            and isinstance(msg, CameraNodeOutputMessage)
                            and msg.camera_id in buffer
                            and msg.charuco_observation is not None
                        ):
                            # Key by connection frame number, not arrival order,
                            # so dropped frames leave gaps instead of shifting indices.
                            buffer[msg.camera_id][msg.frame_number] = msg.charuco_observation
                    except Empty:
                        break
                    except (OSError, EOFError):
                        # Queue closed during shutdown on Windows
                        break

        except Exception:
            logger.exception("CharucoRecorderNode crashed")
        finally:
            # Flush if still recording on shutdown
            if is_recording:
                logger.warning(
                    "CharucoRecorderNode shutting down while recording active — "
                    "flushing partial buffer"
                )
                _flush_buffer(
                    buffer=buffer,
                    recording_info=recording_info,
                    board_config=board_config,
                )
            logger.info("CharucoRecorderNode exiting")


def _flush_buffer(
    *,
    buffer: dict[CameraIdString, dict[int, CharucoObservation]],
    recording_info,
    board_config: CharucoBoardDefinition,
) -> None:
    """Write the buffer to a pickle file.

    ``observations`` maps camera_id -> {connection_frame_number: CharucoObservation}.
    The connection frame number is the stable identifier shared with the recording's
    per-camera timestamps CSV, so posthoc calibration can align each recorded video
    frame to its realtime observation regardless of how many frames realtime dropped.
    """
    if recording_info is None:
        logger.warning("No recording_info — cannot flush buffer")
        return

    recording_path = Path(recording_info.full_recording_path)
    output_dir = recording_path / OUTPUT_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / CACHE_FILENAME

    # Frame range is expressed in connection frame numbers (min/max seen), for
    # diagnostics only — posthoc lookups are per-frame, never by range.
    all_conn_numbers = [
        frame_number
        for obs_by_frame in buffer.values()
        for frame_number in obs_by_frame
    ]
    if not all_conn_numbers:
        logger.info("Buffer is empty — writing empty cache")
        first_frame = last_frame = 0
    else:
        first_frame = min(all_conn_numbers)
        last_frame = max(all_conn_numbers)

    cache_data = {
        "board_definition": board_config,
        "observations": buffer,
        "frame_range": (first_frame, last_frame),
        "recording_uuid": recording_info.recording_uuid if recording_info else "",
    }

    with open(cache_path, "wb") as f:
        pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    total_obs = sum(len(v) for v in buffer.values())
    logger.info(
        f"Wrote {total_obs} observations ({len(buffer)} cameras) to {cache_path}"
    )
