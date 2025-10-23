import logging
import uuid
from abc import ABC
from dataclasses import dataclass
from typing import Hashable

import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraIdString, WorkerStrategy

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


class Point3d(BaseModel):
    x: float
    y: float
    z: float


class BaseAggregationLayerOutputData(BasePipelineData):
    multi_frame_number: int
    points3d: dict[Hashable, Point3d]


class BaseCameraNodeOutputData(BasePipelineData):
    frame_metadata: np.recarray  # dtype: FRAME_METADATA_DTYPE
    time_to_retrieve_frame_ns: int
    time_to_process_frame_ns: int


class BasePipelineOutputData(BasePipelineData):
    camera_node_output: dict[CameraIdString, BaseCameraNodeOutputData]
    aggregation_layer_output: BaseAggregationLayerOutputData

    @property
    def multi_frame_number(self) -> int:
        frame_numbers = [camera_node_output.frame_metadata.frame_number for camera_node_output in
                         self.camera_node_output.values()]
        if len(set(frame_numbers)) > 1:
            raise ValueError(f"Frame numbers from camera nodes do not match - got {frame_numbers}")
        return frame_numbers[0]


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
                          camera_node_strategy: WorkerStrategy = WorkerStrategy.PROCESS,
                          aggregation_node_strategy: WorkerStrategy = WorkerStrategy.PROCESS,
                          ):

        ipc = PipelineIPC.create(global_kill_flag=camera_group.ipc.global_kill_flag,
                                 )
        camera_group_shm_dto = camera_group.shm.to_dto()
        camera_nodes = {camera_id: CameraNode.create(camera_id=camera_id,
                                                     camera_shm_dto=camera_group_shm_dto.camera_shm_dtos[camera_id],
                                                     worker_strategy=camera_node_strategy,
                                                     config=pipeline_config.camera_node_configs[camera_id],
                                                     ipc=ipc)
                        for camera_id, config in camera_group.configs.items()}
        aggregation_node = AggregationNode.create(camera_group_id=camera_group.id,
                                                  config=pipeline_config.aggregation_node_config,
                                                  camera_group_shm_dto=camera_group_shm_dto,
                                                  ipc=ipc,
                                                  worker_strategy=aggregation_node_strategy,
                                                  )

        return cls(camera_nodes=camera_nodes,
                   aggregation_node=aggregation_node,
                   ipc=ipc,
                   id=str(uuid.uuid4())[:6],
                   config=pipeline_config
                   )

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} with camera processes {list(self.camera_nodes.keys())}...")
        self.aggregation_node.start()
        for camera_id, camera_node in self.camera_nodes.items():
            camera_node.start()

    def shutdown(self):
        logger.debug(f"Shutting down {self.__class__.__name__}...")

        self.ipc.global_kill_flag.value = True
        self.aggregation_node.stop()
        for camera_id, camera_process in self.camera_nodes.items():
            camera_process.stop()
