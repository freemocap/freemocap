"""Single-threaded lockstep driver for the realtime pipeline.

Writes one frame at a time into the mock camera group's shared memory and waits
for the aggregator to publish its result before writing the next frame:

    write N -> wait for aggregation output >= N -> flip backpressure events -> write N+1

Because the ring buffer holds far more than 222 frames and we never let the write
head run ahead of consumption, every frame is processed deterministically with no
threading races. (Dumping all frames at once would instead exercise realtime
drop-frame semantics, where the aggregator only processes the latest frame.)
"""
import queue
import time
from dataclasses import dataclass

from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage


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
    outputs: list[AggregationNodeOutputMessage] = []
    sub = pipeline.aggregation_output_subscription

    # Initial backpressure state from RealtimePipeline.create: consumed set,
    # ready clear — so the aggregator may produce its first frame immediately.
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

        # Release the aggregator to process the next frame, mirroring the
        # websocket consumer (RealtimePipeline.get_latest_frontend_payload).
        pipeline.result_ready_event.clear()
        pipeline.result_consumed_event.set()

    return RealtimeDriveResult(outputs=outputs, frames_written=num_frames)
