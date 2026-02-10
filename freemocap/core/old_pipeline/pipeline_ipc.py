import multiprocessing
import uuid
from dataclasses import dataclass, field

from skellycam.core.ipc.pubsub.pubsub_topics import SetShmTopic

from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pubsub.pubsub_manager import PubSubTopicManager, create_pipeline_pubsub_manager
from freemocap.system.logging_configuration.handlers.websocket_log_queue_handler import get_websocket_log_queue
from freemocap.utilities.check_main_processs_heartbeat import check_main_process_heartbeat


@dataclass
class PipelineIPC:
    pipeline_id: PipelineIdString
    pubsub: PubSubTopicManager
    ws_queue: multiprocessing.Queue
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    pipeline_shutdown_flag: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value('b', False))

    @classmethod
    def create(cls,
               global_kill_flag: multiprocessing.Value,
               heartbeat_timestamp: multiprocessing.Value,
               pipeline_id: PipelineIdString | None = None):
        if pipeline_id is None:
            pipeline_id = str(uuid.uuid4())[:6]
        pubsub = create_pipeline_pubsub_manager(pipeline_id=pipeline_id)
        return cls(
            pipeline_id=pipeline_id,
            pubsub=pubsub,
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=heartbeat_timestamp,
            ws_queue=get_websocket_log_queue(),
        )

    @property
    def should_continue(self) -> bool:
        return (not self.global_kill_flag.value
                and not self.pipeline_shutdown_flag.value
                and check_main_process_heartbeat(global_kill_flag=self.global_kill_flag,
                                                 heartbeat_timestamp=self.heartbeat_timestamp, ))

    def shutdown_pipeline(self):
        self.pipeline_shutdown_flag.value = True
        self.pubsub.close()

    def kill_everything(self):
        self.shutdown_pipeline()
        self.global_kill_flag.value = True

