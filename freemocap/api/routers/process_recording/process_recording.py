import logging

from fastapi import APIRouter, Body

from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import process_recording_folder
from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel

logger = logging.getLogger(__name__)
process_recording_router = APIRouter()

@process_recording_router.get("/process", summary="👋")
async def process_recording(processing_config = Body(ProcessingParameterModel(), examples=[ProcessingParameterModel()])):
    process_recording_folder(processing_config)
    return
