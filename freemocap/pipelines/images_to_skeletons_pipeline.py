from typing import Dict

from freemocap.pipelines.pipeline_abcs import PipelineStageConfig, PipelineConfig, PipelineData, PipelineStage, \
    PipelineModel


class SkellyTrackerConfig(PipelineStageConfig):
    model_complexity: int = 1

class SkellyForgeConfig(PipelineStageConfig):
    confidence_threshold: float = 0.5


class ImagesToSkeletonPipelineConfig(PipelineConfig):
    stage_configs: Dict[str, PipelineStageConfig] = {
        "skellytracker": SkellyTrackerConfig(),
        "skellyforge" : SkellyForgeConfig()
    }

class ImagesToSkeletonPipeline(PipelineModel):
    config: ImagesToSkeletonPipelineConfig = ImagesToSkeletonPipelineConfig()

    def process_data(self, data: PipelineData) -> PipelineData:
        return super().process_data(data)
