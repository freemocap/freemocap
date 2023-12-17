import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

import logging

from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel

core_process_router = APIRouter()

logger = logging.getLogger(__name__)


@core_process_router.post("/process/{recording_path}")
async def process_recording_folder_endpoint(recording_folder: str,
                                            processing_config: ProcessingParameterModel = ProcessingParameterModel()
                                            ) -> ProcessingParameterModel:
    await asyncio.sleep(1)
    return processing_config
