"""Start work on an existing recording; inspect saved stages independently."""
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from freemocap.api.http.mocap import mocap_router as mocap
from freemocap.api.http.calibration import calibration_router as calibration
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.api.http.recordings.recording_location import recording_location
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig

processing_router = APIRouter(prefix='/recordings')
stage_reads = APIRouter(route_class=RecordingReadRoute)


class MocapProcessingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['mocap']
    config: PosthocMocapPipelineConfig = Field(default_factory=PosthocMocapPipelineConfig)


class CalibrationProcessingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['calibration']
    config: PosthocCalibrationPipelineConfig = Field(default_factory=PosthocCalibrationPipelineConfig)


ProcessingRequest = Annotated[MocapProcessingRequest | CalibrationProcessingRequest, Field(discriminator='kind')]


class ProcessingAccepted(BaseModel):
    task_id: str
    status_url: str
    recording_id: str
    recording_parent_directory: str


@processing_router.post('/{recording_id}/processing', status_code=202, tags=['Recording processing'])
async def process_recording(recording_id: str, request: ProcessingRequest, http_request: Request,
                            recording_parent_directory: str | None = None) -> ProcessingAccepted:
    structure = recording_location(recording_id, recording_parent_directory)
    if request.kind == 'mocap':
        result = await mocap.process_mocap_recording(mocap.ProcessMocapRecordingRequest(
            mocap_recording_directory=str(structure.full_path), mocap_config=request.config), http_request)
    else:
        result = await calibration.calibrate_recording(calibration.CalibrateRecordingRequest(
            calibration_recording_directory=str(structure.full_path), calibration_config=request.config))
    if not result.pipeline_id:
        raise HTTPException(500, 'Processing did not return a task ID')
    return ProcessingAccepted(task_id=result.pipeline_id, status_url=f'/freemocap/tasks/{result.pipeline_id}',
        recording_id=structure.recording_name, recording_parent_directory=str(structure.base_directory))


class StageReadiness(BaseModel):
    observations: bool
    triangulation: bool
    filtering: bool
    scale_fit: bool
    reconstruction: bool


class GroupStages(BaseModel):
    sensor_group: str
    stages: StageReadiness


class RunStages(BaseModel):
    run_id: int
    groups: list[GroupStages]


class StageInventory(BaseModel):
    runs: list[RunStages]
    selected_run_id: int


@stage_reads.get('/{recording_id}/stages', tags=['Recording results'])
def saved_stages(recording_id: str, recording_parent_directory: str | None = None) -> StageInventory:
    structure = recording_location(recording_id, recording_parent_directory)
    return StageInventory.model_validate(mocap.saved_mocap_stages(str(structure.full_path)))


@stage_reads.get('/{recording_id}/runs/{run_id}/stages', tags=['Recording results'])
def run_stages(recording_id: str, run_id: int, recording_parent_directory: str | None = None) -> RunStages:
    inventory = saved_stages(recording_id, recording_parent_directory)
    for run in inventory.runs:
        if run.run_id == run_id:
            return run
    raise HTTPException(404, f'Unknown recording run: {run_id}')


processing_router.include_router(stage_reads)
