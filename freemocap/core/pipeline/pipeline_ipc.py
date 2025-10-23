import multiprocessing
import uuid
from dataclasses import dataclass, field

from freemocap.core.pubsub.pubsub_manager import PubSubTopicManager, create_pipeline_pubsub_manager
from freemocap.core.types.type_overloads import PipelineIdString

from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO

@dataclass
class PipelineIPC:
    pubsub: PubSubTopicManager
    pipeline_id: PipelineIdString
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_flag: multiprocessing.Value = field(default_factory=lambda: multiprocessing.Value('b', False))

    @classmethod
    def create(cls,
               global_kill_flag: multiprocessing.Value,
               pipeline_id: PipelineIdString | None = None):
        if pipeline_id is None:
            pipeline_id = str(uuid.uuid4())[:6]
        pubsub = create_pipeline_pubsub_manager(pipeline_id=pipeline_id)
        return cls(
            pipeline_id=pipeline_id,
            pubsub=pubsub,
            global_kill_flag=global_kill_flag,
        )

    def should_continue(self) -> bool:
        return not self.global_kill_flag.value and not self.pipeline_shutdown_flag.value

    def shutdown_pipeline(self):
        self.pipeline_shutdown_flag.value = True
        self.pubsub.close()

    def kill_everything(self):
        self.shutdown_pipeline()
        self.global_kill_flag.value = True
