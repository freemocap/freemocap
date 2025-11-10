import logging
import multiprocessing
import uuid

from pydantic import BaseModel, ConfigDict

from freemocap.core.pipeline.pipeline_configs import MocapTaskConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_aggregation_node import PosthocMocapAggregationNode
from freemocap.core.pipeline.posthoc_pipelines.video_group import VideoGroup
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_video_node import  MocapVideoNode
from freemocap.core.types.type_overloads import PipelineIdString, VideoIdString

from skellycam.core.recorders.videos.recording_info import RecordingInfo

logger = logging.getLogger(__name__)





class PosthocMocapProcessingPipeline(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )
    id: PipelineIdString
    recording_info:RecordingInfo
    mocap_task_config: MocapTaskConfig
    video_nodes: dict[VideoIdString, MocapVideoNode]
    aggregation_node: PosthocMocapAggregationNode
    ipc: PipelineIPC
    started: bool = False

    @property
    def alive(self) -> bool:
        return all([video_node.worker.is_alive() for video_node in
                    self.video_nodes.values()]) and self.aggregation_node.worker.is_alive()

    @property
    def video_ids(self) -> list[VideoIdString]:
        return list(self.video_nodes.keys())

    @classmethod
    def from_task_config(cls,
                    recording_info:RecordingInfo,
                    heartbeat_timestamp: multiprocessing.Value,
                    subprocess_registry: list[multiprocessing.Process],
                    mocap_task_config: MocapTaskConfig,
                    global_kill_flag: multiprocessing.Value,
                    ):
        #validate by creating video_group object
        video_group = VideoGroup.from_recording_path(recording_path=recording_info.full_recording_path)
        pipeline_id = str(uuid.uuid4())[:6]
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
                                 heartbeat_timestamp=heartbeat_timestamp
                                 )
        video_nodes = {video_id: MocapVideoNode.create(video_path=video_helper.video_path,  #recreate in node worker
                                                             subprocess_registry=subprocess_registry,
                                                             mocap_task_config=mocap_task_config,
                                                             ipc=ipc)
                       for video_id, video_helper in video_group.videos.items()}
        aggregation_node = PosthocMocapAggregationNode.create(subprocess_registry=subprocess_registry,
                                                                    mocap_task_config=mocap_task_config,
                                                                    video_metadata=video_group.video_metadata_by_id,
                                                                    ipc=ipc,
                                                                    recording_info=recording_info,
                                                                    pipeline_id=pipeline_id
                                                                    )
        video_group.close()  # close here, videos reopened in video nodes
        return cls(video_nodes=video_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   mocap_task_config=mocap_task_config,
                   id=pipeline_id,
                   recording_info=recording_info
                   )

    def start(self) -> None:
        self.started = True
        logger.debug(f"Starting Pipeline (id:{self.id} with  for recording: {self.recording_info.recording_name}")
        try:
            logger.debug("Starting video nodes...")
            [node.start() for node in self.video_nodes.values()]
        except Exception as e:
            logger.error(f"Failed to start video nodes: {type(e).__name__} - {e}")
            logger.exception(e)
            raise

        try:
            logger.debug("Starting aggregation node...")
            self.aggregation_node.start()
            logger.debug(f"Aggregation node worker started: alive={self.aggregation_node.worker.is_alive()}")
        except Exception as e:
            logger.error(f"Failed to start aggregation node: {type(e).__name__} - {e}")
            logger.exception(e)
            raise


        logger.info(f"All pipeline workers started successfully")

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.shutdown_pipeline()
        for video_id, video_node in self.video_nodes.items():
            video_node.shutdown()
        self.aggregation_node.shutdown()
