import logging
from abc import ABC, abstractmethod
from multiprocessing import Process, Queue
from typing import Dict, OrderedDict

from pydantic import BaseModel, Field
from skellycam.core import CameraId

logger = logging.getLogger(__name__)


class PipelineStageConfig(BaseModel, ABC):
    pass


class PipelineConfig(BaseModel, ABC):
    stage_configs: Dict[str, PipelineStageConfig]


class PipelineData(BaseModel, ABC):
    data: object
    metadata: dict[object, object] = Field(default_factory=dict)


class PipelineStage(BaseModel, ABC):
    config: PipelineConfig

    @abstractmethod
    def get_output(self, input_data: PipelineData) -> PipelineData:
        pass


class PipelineModel(BaseModel, ABC):
    config: PipelineConfig
    stages: OrderedDict[str, PipelineStage]

    def process_data(self, data: PipelineData) -> PipelineData:
        logger.loop("Running pipeline")
        latest_data = data
        for stage in self.stages.values():
            logger.info(f"Running stage {stage}")
            latest_data = stage.process_input(latest_data)
        return latest_data


class CameraProcessingNode(BaseModel, ABC):
    camera_id: CameraId
    process: Process
    input_queue: Queue
    output_queue: Queue

    @classmethod
    def create(cls,
               config: PipelineConfig,
               camera_id: CameraId,
               input_queue: Queue,
               output_queue: Queue):
        pass

    def start(self):
        self.process.start()

    def stop(self):
        self.process.terminate()

    def join(self):
        self.process.join()

class ProcessTree(ABC):
    camera_processes: Dict[CameraId, CameraProcessingNode]
    aggregation_process: Process
    queues_by_camera_id: Dict[CameraId, Queue]
    output_queue: Queue


class ProcessingServer(BaseModel, ABC):
    process_tree: ProcessTree

    def process_data(self, data: PipelineData) -> PipelineData:
        return self.pipeline.process_data(data)
