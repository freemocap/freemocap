import logging
from copy import deepcopy
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.pipeline_configs import CalibrationPipelineConfig
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

logger = logging.getLogger(__name__)

calibration_router = APIRouter(prefix="/calibration", tags=["Calibration"])


# ==================== Request/Response Models ====================


class CalibrationConfigRequest(BaseModel):
    config: CalibrationPipelineConfig


class CalibrationConfigResponse(BaseModel):
    success: bool
    message: str | None = None

def _calibrate_request_schema_extra(schema: dict) -> None:
    schema["examples"] = [CalibrateRecordingRequest.create_test_data_request().model_dump(by_alias=True)]


class CalibrateRecordingRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra=_calibrate_request_schema_extra,
    )
    calibration_config: CalibrationPipelineConfig = Field(
        alias="calibrationTaskConfig",
        default_factory=CalibrationPipelineConfig,
    )
    calibration_recording_directory: str | None = Field(
        alias="calibrationRecordingDirectory",
        description="Optional directory for calibration recording.")

    def to_recording_info(self) -> RecordingInfo:
        if self.calibration_recording_directory is None:
            raise RuntimeError("CalibrationConfig.calibration_recording_directory not set")
        recording_dir = Path(self.calibration_recording_directory).expanduser()
        return RecordingInfo(
            recording_directory=str(recording_dir.parent),
            recording_name=recording_dir.stem,
            mic_device_index=-1,
        )

    @classmethod
    def create_test_data_request(cls) -> "CalibrateRecordingRequest":
        config = CalibrationPipelineConfig()

        config.charuco_board_x_squares = 7
        config.charuco_board_y_squares = 5
        config.charuco_square_length = 54
        return cls(calibration_config=config,
                   calibration_recording_directory = FREEMOCAP_TEST_DATA_PATH)




class StopCalibrationRecordingRequest(BaseModel):
    calibration_config: CalibrationPipelineConfig = Field(alias="calibrationTaskConfig")





class StartCalibrationRecordingResponse(BaseModel):
    success: bool
    message: str | None = None


class CalibrateRecordingResponse(BaseModel):
    success: bool
    message: str | None = None
    results: dict | None = None


# ==================== Endpoints ====================


@calibration_router.post("/config/update/all")
def update_all_calibration_config(request: CalibrationConfigRequest) -> CalibrationConfigResponse:
    """Update calibration configuration on all active realtime pipelines via SettingsManager."""
    try:
        app = get_freemocap_app()

        # Update settings manager (source of truth), which notifies WebSocket clients
        app.settings_manager.apply_patch({
            "calibration": {"config": request.config.model_dump()},
        })

        # Sync to running pipelines
        with app.realtime_pipeline_manager.lock:
            for pipeline in app.realtime_pipeline_manager.pipelines.values():
                new_config = deepcopy(pipeline.config)
                new_config.calibration_config = request.config
                pipeline.update_config(new_config=new_config)

        return CalibrationConfigResponse(success=True, message="Configuration updated")
    except Exception as e:
        logger.exception(f"Error updating calibration config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/start")
async def start_calibration_recording(
    request: CalibrateRecordingRequest,
) -> StartCalibrationRecordingResponse:
    """Start calibration recording with given config."""
    try:
        recording_info = request.to_recording_info()
        await get_freemocap_app().start_recording_all(recording_info=recording_info)
        logger.info(f"Starting calibration recording: {recording_info}")
        return StartCalibrationRecordingResponse(success=True, message="Recording started")
    except Exception as e:
        logger.exception(f"Error starting calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/stop")
async def stop_calibration_recording(
    request: StopCalibrationRecordingRequest,
) -> dict[str, bool]:
    """Stop current calibration recording and launch posthoc calibration pipeline."""
    app = get_freemocap_app()
    try:
        recording_info = await app.stop_recording_all()
        if recording_info is None:
            raise RuntimeError("No active recording to stop")
        await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info("Calibration recording stopped, posthoc calibration pipeline launched")
        return {"success": True}
    except Exception as e:
        logger.exception(f"Error stopping calibration recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@calibration_router.post("/recording/calibrate")
async def calibrate_recording(request: CalibrateRecordingRequest) -> CalibrateRecordingResponse:
    """Process and calibrate a previously recorded session."""
    app = get_freemocap_app()
    try:

        recording_info = request.to_recording_info()
        await app.create_posthoc_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=request.calibration_config,
        )
        logger.info(f"Calibrating recording at: {recording_info.full_recording_path}")
        return CalibrateRecordingResponse(
            success=True,
            message="Calibration pipeline launched",
            results={},
        )
    except Exception as e:
        logger.exception(f"Error calibrating recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ApplyFeetGroundplaneRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recording_folder: str = Field(alias="recordingFolder")
    force: bool = Field(
        default=False,
        description="Re-estimate groundplane even if one was already applied.",
    )


class ApplyFeetGroundplaneResponse(BaseModel):
    success: bool
    message: str | None = None
    method: str | None = None


# @calibration_router.post("/apply-feet-groundplane")
# def apply_feet_groundplane(
#     request: ApplyFeetGroundplaneRequest,
# ) -> ApplyFeetGroundplaneResponse:
#     """Manually apply feet-based ground plane to an existing calibration.
#
#     Loads the calibration TOML and skeleton 3D data from the recording folder,
#     estimates the ground plane from foot markers, updates the camera extrinsics,
#     and re-saves the TOML.
#
#     Skips if groundplane was already applied, unless force=True.
#     """
#     try:
#         recording_folder = Path(request.recording_folder).expanduser()
#         output_folder = recording_folder / "output_data"
#
#         # Find calibration TOML in recording folder
#         toml_candidates = list(recording_folder.glob("*_camera_calibration.toml"))
#         if not toml_candidates:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"No calibration TOML found in {recording_folder}",
#             )
#         calibration_toml_path = toml_candidates[0]
#
#         # Check if groundplane already applied
#         if not request.force:
#             toml_data = toml.loads(calibration_toml_path.read_text())
#             metadata = toml_data.get("metadata", {})
#             if metadata.get("groundplane_applied", False):
#                 return ApplyFeetGroundplaneResponse(
#                     success=True,
#                     message=f"Groundplane already applied (method: {metadata.get('groundplane_method', 'unknown')}). Use force=true to re-estimate.",
#                     method=metadata.get("groundplane_method"),
#                 )
#
#         # Load skeleton 3D body data
#         body_npy_candidates = list(output_folder.glob("*body*3d*.npy"))
#         if not body_npy_candidates:
#             # Try the combined skeleton file
#             body_npy_candidates = list(output_folder.glob("*skeleton_3d.npy"))
#
#         if not body_npy_candidates:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"No body 3D data found in {output_folder}",
#             )
#
#         body_3d = np.load(body_npy_candidates[0])
#         marker_name_to_index = build_mediapipe_body_marker_name_to_index()
#
#         # If we loaded the full skeleton (body+hands+face), take only body portion (first 33)
#         if body_3d.shape[1] > 33:
#             body_3d = body_3d[:, :33, :]
#
#         ground_plane = estimate_groundplane_from_feet(
#             skeleton_3d=body_3d,
#             marker_name_to_index=marker_name_to_index,
#         )
#
#         if ground_plane is None:
#             return ApplyFeetGroundplaneResponse(
#                 success=False,
#                 message="Could not estimate ground plane from foot markers (missing data or markers)",
#             )
#
#         # Load calibration, apply, re-save
#         calibration = CalibrationResult.load_anipose_toml(calibration_toml_path)
#         updated_cameras = apply_groundplane_to_cameras(calibration.cameras, ground_plane)
#
#         toml_data = toml.loads(calibration_toml_path.read_text())
#         existing_metadata = toml_data.get("metadata", {})
#         existing_metadata.update(groundplane_metadata(ground_plane, recording_folder.stem))
#
#         updated_result = CalibrationResult(
#             cameras=updated_cameras,
#             board=calibration.board,
#             reprojection_error_px=calibration.reprojection_error_px,
#             initial_cost=calibration.initial_cost,
#             final_cost=calibration.final_cost,
#             n_iterations=calibration.n_iterations,
#             time_seconds=calibration.time_seconds,
#             n_observations_used=calibration.n_observations_used,
#             n_observations_rejected=calibration.n_observations_rejected,
#         )
#         updated_result.dump_anipose_toml(
#             path=calibration_toml_path,
#             metadata=numpy_to_python(existing_metadata),
#         )
#
#         return ApplyFeetGroundplaneResponse(
#             success=True,
#             message="Feet-based ground plane applied to calibration",
#             method="feet",
#         )
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception(f"Error applying feet ground plane: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
