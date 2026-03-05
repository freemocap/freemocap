"""
PipelineIPC: shared inter-process communication flags for a single pipeline.

Contains only the cross-process primitives that children need:
  - pipeline_id
  - global_kill_flag / pipeline_shutdown_flag
  - heartbeat_timestamp
  - ws_queue (for log forwarding)

PubSub is NOT on this object. Pipelines own pubsub separately and pass
bare queue handles to children as explicit kwargs.
"""
import multiprocessing
import uuid
from dataclasses import dataclass, field

from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from freemocap.utilities.check_main_processs_heartbeat import check_main_process_heartbeat


@dataclass
class PipelineIPC:
    pipeline_id: PipelineIdString
    ws_queue: multiprocessing.Queue
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    pipeline_shutdown_flag: multiprocessing.Value = field(
        default_factory=lambda: multiprocessing.Value('b', False),
    )

    @classmethod
    def create(
        cls,
        *,
        global_kill_flag: multiprocessing.Value,
        heartbeat_timestamp: multiprocessing.Value,
        pipeline_id: PipelineIdString | None = None,
    ) -> "PipelineIPC":
        if pipeline_id is None:
            pipeline_id = str(uuid.uuid4())[:6]
        return cls(
            pipeline_id=pipeline_id,
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=heartbeat_timestamp,
            ws_queue=get_websocket_log_queue(),
        )

    @property
    def should_continue(self) -> bool:
        return (
            not self.global_kill_flag.value
            and not self.pipeline_shutdown_flag.value
            and check_main_process_heartbeat(
                global_kill_flag=self.global_kill_flag,
                heartbeat_timestamp=self.heartbeat_timestamp,
            )
        )

    def shutdown_pipeline(self) -> None:
        """Signal this pipeline to stop. Does NOT touch the global kill flag."""
        self.pipeline_shutdown_flag.value = True

    def kill_everything(self) -> None:
        """Nuclear option: stop this pipeline AND signal global shutdown."""
        self.pipeline_shutdown_flag.value = True
        self.global_kill_flag.value = True