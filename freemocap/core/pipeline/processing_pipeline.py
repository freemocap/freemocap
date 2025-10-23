import logging
import uuid
from abc import ABC
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.aggregation_node import AggregationNode
from freemocap.core.pipeline.camera_node import CameraNode
from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


class BasePipelineData(BaseModel, ABC):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )
    pass


@dataclass
class ProcessingPipeline:
    id: PipelineIdString
    config: PipelineConfig
    camera_nodes: dict[CameraIdString, CameraNode]
    aggregation_node: AggregationNode
    ipc: PipelineIPC

    @property
    def alive(self) -> bool:
        return all([camera_node.worker.is_alive() for camera_node in
                    self.camera_nodes.values()]) and self.aggregation_node.worker.is_alive()

    @classmethod
    def from_camera_group(cls,
                          camera_group: CameraGroup,
                          pipeline_config: PipelineConfig,
                          ):

        ipc = PipelineIPC.create(global_kill_flag=camera_group.ipc.global_kill_flag,
                                 )
        camera_group_shm_dto = camera_group.shm.to_dto()
        camera_nodes = {camera_id: CameraNode.create(camera_id=camera_id,
                                                     camera_shm_dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                                                     config=pipeline_config.camera_node_configs[camera_id],
                                                     ipc=ipc)
                        for camera_id, config in camera_group.configs.items()}
        aggregation_node = AggregationNode.create(camera_group_id=camera_group.id,
                                                  config=pipeline_config.aggregation_node_config,
                                                  camera_group_shm_dto=camera_group_shm_dto,
                                                  ipc=ipc,
                                                  )

        return cls(camera_nodes=camera_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   id=str(uuid.uuid4())[:6],
                   config=pipeline_config
                   )

    def start(self) -> None:
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {list(self.camera_nodes.keys())}...")

        try:
            logger.debug("Starting aggregation node...")
            self.aggregation_node.start()
            logger.debug(f"Aggregation node worker started: alive={self.aggregation_node.worker.is_alive()}")
        except Exception as e:
            logger.error(f"Failed to start aggregation node: {type(e).__name__} - {e}")
            logger.exception(e)
            raise

        for camera_id, camera_node in self.camera_nodes.items():
            try:
                logger.debug(f"Starting camera node {camera_id}...")
                camera_node.start()
                logger.debug(f"Camera node {camera_id} worker started: alive={camera_node.worker.is_alive()}")
            except Exception as e:
                logger.error(f"Failed to start camera node {camera_id}: {type(e).__name__} - {e}")
                logger.exception(e)
                raise

        logger.info(f"All pipeline workers started successfully")
    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.global_kill_flag.value = True
        self.aggregation_node.stop()
        for camera_id, camera_process in self.camera_nodes.items():
            camera_process.stop()
