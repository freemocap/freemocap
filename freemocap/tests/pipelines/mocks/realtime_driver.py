"""Single-threaded lockstep driver for the realtime pipeline."""
import logging
import queue
import time
from dataclasses import dataclass

from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage

logger = logging.getLogger(__name__)


@dataclass
class RealtimeDriveResult:
    outputs: list  # list[AggregationNodeOutputMessage], one per processed frame
    frames_written: int

    @property
    def frames_processed(self) -> int:
        return len(self.outputs)


def drive_realtime_lockstep(
    *,
    pipeline,
    mock_group,
    num_frames: int,
    per_frame_timeout: float = 30.0,
) -> RealtimeDriveResult:
    logger.info(
        f"Starting lockstep drive: {num_frames} frames  "
        f"per_frame_timeout={per_frame_timeout}s"
    )
    outputs: list[AggregationNodeOutputMessage] = []
    sub = pipeline.aggregation_output_subscription

    t_start = time.perf_counter()
    last_progress_log = t_start

    for frame_index in range(num_frames):
        mock_group.write_frame(frame_index)

        got: AggregationNodeOutputMessage | None = None
        deadline = time.perf_counter() + per_frame_timeout
        while time.perf_counter() < deadline:
            if not pipeline.alive:
                raise RuntimeError(
                    f"Realtime pipeline died while waiting for frame {frame_index} "
                    f"(processed {len(outputs)} frames). Check worker logs above."
                )
            try:
                msg = sub.get(timeout=0.2)
            except queue.Empty:
                continue
            if isinstance(msg, AggregationNodeOutputMessage) and msg.frame_number >= frame_index:
                got = msg
                break
        if got is None:
            raise TimeoutError(
                f"No aggregation output for frame {frame_index} within "
                f"{per_frame_timeout}s (processed {len(outputs)} frames)."
            )
        outputs.append(got)

        pipeline.result_ready_event.clear()
        pipeline.result_consumed_event.set()

        now = time.perf_counter()
        if now - last_progress_log >= 10.0 or frame_index == num_frames - 1:
            elapsed = now - t_start
            fps = (frame_index + 1) / elapsed if elapsed > 0 else 0.0
            has_kp = len(got.keypoints_arrays) > 0
            has_skel = bool(got.skeleton)
            logger.info(
                f"  frame {frame_index + 1}/{num_frames}  "
                f"elapsed={elapsed:.1f}s  fps={fps:.1f}  "
                f"keypoints={'yes' if has_kp else 'no'}  "
                f"skeleton={'yes' if has_skel else 'no'}"
            )
            last_progress_log = now

    total_elapsed = time.perf_counter() - t_start
    avg_fps = num_frames / total_elapsed if total_elapsed > 0 else 0.0
    frames_with_kp = sum(1 for o in outputs if len(o.keypoints_arrays) > 0)
    logger.info(
        f"Lockstep drive done: {len(outputs)}/{num_frames} frames processed  "
        f"total={total_elapsed:.1f}s  avg_fps={avg_fps:.1f}  "
        f"frames_with_keypoints={frames_with_kp}"
    )
    return RealtimeDriveResult(outputs=outputs, frames_written=num_frames)
