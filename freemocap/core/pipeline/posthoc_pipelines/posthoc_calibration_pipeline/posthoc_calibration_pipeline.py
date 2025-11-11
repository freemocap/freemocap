import logging
import multiprocessing
import uuid

from pydantic import BaseModel, ConfigDict

from freemocap.core.pipeline.pipeline_configs import CalibrationpipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_aggregation_node import PosthocCalibrationAggregationNode
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_video_node import VideoNodeState, CalibrationVideoNode
from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoGroupHelper
from freemocap.core.pipeline.realtime_pipeline.realtime_aggregation_node import RealtimeAggregationNodeState
from freemocap.core.types.type_overloads import PipelineIdString, VideoIdString

from skellycam.core.recorders.videos.recording_info import RecordingInfo

logger = logging.getLogger(__name__)


class PosthocPipelineState(BaseModel):
    """Serializable representation of a processing pipeline state."""
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    id: PipelineIdString
    video_node_states: dict[VideoIdString, VideoNodeState]
    aggregation_node_state: RealtimeAggregationNodeState
    alive: bool

class PosthocCalibrationProcessingPipeline(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )
    id: PipelineIdString
    recording_info:RecordingInfo
    calibration_pipeline_config: CalibrationpipelineConfig
    video_nodes: dict[VideoIdString, CalibrationVideoNode]
    aggregation_node: PosthocCalibrationAggregationNode
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
    def from_config(cls,
                    recording_info:RecordingInfo,
                    heartbeat_timestamp: multiprocessing.Value,
                    subprocess_registry: list[multiprocessing.Process],
                    calibration_pipeline_config: CalibrationpipelineConfig,
                    global_kill_flag: multiprocessing.Value,
                    ):
        #validate with video_group object
        video_group = VideoGroupHelper.from_recording_path(recording_path=recording_info.full_recording_path)
        pipeline_id = str(uuid.uuid4())[:6]
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
                                 heartbeat_timestamp=heartbeat_timestamp
                                 )
        video_nodes = {video_id: CalibrationVideoNode.create(video_path=video_helper.video_path,  #recreate in node worker
                                                             subprocess_registry=subprocess_registry,
                                                             calibration_pipeline_config=calibration_pipeline_config,
                                                             ipc=ipc)
                       for video_id, video_helper in video_group.videos.items()}
        aggregation_node = PosthocCalibrationAggregationNode.create(subprocess_registry=subprocess_registry,
                                                                    calibration_pipeline_config=calibration_pipeline_config,
                                                                    video_metadata=video_group.video_metadata_by_id,
                                                                    ipc=ipc,
                                                                    recording_info=recording_info,
                                                                    pipeline_id=pipeline_id
                                                                    )
        video_group.close()  # close here, videos reopened in video nodes
        return cls(video_nodes=video_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   calibration_pipeline_config=calibration_pipeline_config,
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

