import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from freemocap.data.recording_models.post_processing_parameter_models import ProcessingParameterModel

processing_router = APIRouter()

logger = logging.getLogger(__name__)


class Track2dConfig(BaseModel):
    pass


class Triangulate3dConfig(BaseModel):
    pass


class GapFillConfig(BaseModel):
    pass


class FilterConfig(BaseModel):
    pass


class RigigBodiesConfig(BaseModel):
    pass


class OrientDataConfig(BaseModel):
    pass


class JointAnglesConfig(BaseModel):
    pass


class CenterOfMassConfig(BaseModel):
    pass


class SaveToDiskConfig(BaseModel):
    pass


class ExportToBlenderConfig(BaseModel):
    pass


class GenericPostProcessConfig(BaseModel):
    gap_fill_config: GapFillConfig
    filter_config: FilterConfig


class SemanticPostProcessConfig(BaseModel):
    rigid_bodies_config: RigigBodiesConfig
    orient_data_config: OrientDataConfig


class BiomechanicsConfig(BaseModel):
    joint_angles_config: JointAnglesConfig
    center_of_mass_config: CenterOfMassConfig


class PostProcessConfig(BaseModel):
    generic_post_process_config: GenericPostProcessConfig
    semantic_post_process_config: SemanticPostProcessConfig


class ExportDataConfig(BaseModel):
    save_to_disk_config: SaveToDiskConfig
    export_to_blender_config: ExportToBlenderConfig

def track2d(recording_id: str, track2d_config: Track2dConfig):
    logger.info(f"Tracking 2D data for recording {recording_id} with config {track2d_config}")
    pass

def triangulate3d(recording_id: str, triangulate3d_config: Triangulate3dConfig):
    logger.info(f"Triangulating 3D data for recording {recording_id} with config {triangulate3d_config}")
    pass

def post_process(recording_id: str, post_process_config: PostProcessConfig):
    logger.info(f"Post-processing data for recording {recording_id} with config {post_process_config}")
    pass

def export_data(recording_id: str, export_data_config: ExportDataConfig):
    logger.info(f"Exporting data for recording {recording_id} with config {export_data_config}")
    pass


def run_freemocap_pipeline(recording_id: str, processing_parameters: ProcessingParameterModel):
    logger.info(f"Running FreeMoCap pipeline for recording {recording_id} with parameters {processing_parameters}")
    if processing_parameters.track2d:
        track2d(recording_id, processing_parameters.track2d)

    if processing_parameters.triangulate3d:
        triangulate3d(recording_id, processing_parameters.triangulate3d)

    if processing_parameters.post_process:
        post_process(recording_id, processing_parameters.post_process)

    if processing_parameters.export_data:
        export_data(recording_id, processing_parameters.export_data)


@processing_router.post("{recording_id}/process",
                        summary="Process a recording through the FreeMoCap pipeline",
                        )
async def process_recording_endpoint(recording_id: str,
                            background_tasks: BackgroundTasks,
                            processing_parameters: ProcessingParameterModel = ProcessingParameterModel()):
    """
    A simple endpoint to process a recording through the FreeMoCap pipeline.
    """
    logger.api(f"Processing recording {recording_id} with parameters {processing_parameters}")

    background_tasks.add_task(run_freemocap_pipeline, recording_id, processing_parameters)


@processing_router.post("{recording_id}/process/2d/track")
async def track2d_endpoint(recording_id: str,
                  background_tasks: BackgroundTasks,
                  track2d_config: Track2dConfig = Track2dConfig()):
    logger.api(f"Tracking 2D data for recording {recording_id} with config {track2d_config}")
    background_tasks.add_task(track2d, recording_id, track2d_config)


@processing_router.post("{recording_id}/process/3d/triangulate")
async def triangulate3d_endpoint(recording_id: str,
                        background_tasks: BackgroundTasks,
                        triangulate3d_config: Triangulate3dConfig = Triangulate3dConfig()):
    background_tasks.add_task(triangulate3d, recording_id, triangulate3d_config)


@processing_router.post("{recording_id}/process/post")
async def post_process_endpoint(recording_id: str,
                       background_tasks: BackgroundTasks,
                       post_process_config: PostProcessConfig = PostProcessConfig()):
    background_tasks.add_task(post_process, recording_id, post_process_config)

@processing_router.post("{recording_id}/process/export")
async def export_data_endpoint(recording_id: str,
                      background_tasks: BackgroundTasks,
                      export_data_config: ExportDataConfig = ExportDataConfig()):
    background_tasks.add_task(export_data, recording_id, export_data_config)