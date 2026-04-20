import inspect
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.blender.export_to_blender import export_to_blender
from freemocap.core.blender.helpers.install_blender_addon import \
    install_freemocap_blender_addon
from freemocap.core.blender.helpers.get_best_guess_of_blender_path import get_best_guess_of_blender_path
from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

logger = logging.getLogger(__name__)

blender_router = APIRouter(prefix="/blender", tags=["Blender"])


# ==================== Request/Response Models ====================


class DetectBlenderResponse(BaseModel):
    blender_exe_path: str | None = None
    found: bool
    message: str | None = None


class InstallAddonRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"blenderExePath": None}},
    )
    blender_exe_path: str | None = Field(alias="blenderExePath", default=None, examples=[None])


class InstallAddonResponse(BaseModel):
    success: bool
    message: str | None = None


class ExportToBlenderRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "recordingFolderPath": FREEMOCAP_TEST_DATA_PATH,
                "blenderExePath": None,
                "autoOpenBlendFile": True,
            }
        },
    )
    recording_folder_path: str = Field(alias="recordingFolderPath", default=FREEMOCAP_TEST_DATA_PATH)
    blender_exe_path: str | None = Field(alias="blenderExePath", default=None, examples=[None])
    auto_open_blend_file: bool = Field(alias="autoOpenBlendFile", default=True)

    @property
    def blend_file_path(self):
        recording_name = Path(self.recording_folder_path).stem
        return str(Path(self.recording_folder_path) /f"{recording_name}.blend")



class ExportToBlenderResponse(BaseModel):
    success: bool
    message: str | None = None
    blender_file_path: str | None = None


# ==================== Endpoints ====================


@blender_router.get("/detect")
def detect_blender() -> DetectBlenderResponse:
    """Detect the Blender executable on the user's system."""
    try:
        blender_path = get_best_guess_of_blender_path()
        if blender_path is None:
            return DetectBlenderResponse(
                found=False,
                message="Could not find a Blender installation on this system",
            )
        return DetectBlenderResponse(
            blender_exe_path=str(blender_path),
            found=True,
            message=f"Found Blender at: {blender_path}",
        )
    except Exception as e:
        logger.exception(f"Error detecting Blender: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@blender_router.post("/addon/install")
def install_addon(request: InstallAddonRequest) -> InstallAddonResponse:
    """Install the freemocap_blender_addon into Blender (optional, not required for export)."""
    try:
        if request.blender_exe_path is None:
            request.blender_exe_path = get_best_guess_of_blender_path()
        blender_exe = Path(request.blender_exe_path)
        if not blender_exe.is_file():

            raise HTTPException(status_code=400, detail=f"Blender executable not found at: {request.blender_exe_path}")

        from freemocap_blender_addon.main import ajc27_run_as_main_function
        ajc_addon_main_file_path = inspect.getfile(ajc27_run_as_main_function)

        install_freemocap_blender_addon(
            blender_exe_path=str(blender_exe),
            ajc_addon_main_file_path=ajc_addon_main_file_path,
        )
        return InstallAddonResponse(success=True, message="Addon installed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error installing addon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@blender_router.post("/export")
def export_to_blender_endpoint(request: ExportToBlenderRequest) -> ExportToBlenderResponse:
    """Export a recording session to a .blend file. Works without addon installation."""
    try:
        recording_folder = Path(request.recording_folder_path)
        if not recording_folder.is_dir():
            raise HTTPException(status_code=400, detail=f"Recording folder not found: {request.recording_folder_path}")
        if request.blender_exe_path is None:
            request.blender_exe_path = get_best_guess_of_blender_path()
        blender_exe = Path(request.blender_exe_path)
        if not blender_exe.is_file():
            raise HTTPException(status_code=400, detail=f"Blender executable not found at: {request.blender_exe_path}")

        export_to_blender(
            recording_folder_path=str(recording_folder),
            blend_file_path=request.blend_file_path,
            blender_exe_path=str(blender_exe),
            open_file_on_completion=request.auto_open_blend_file,
        )
        return ExportToBlenderResponse(
            success=True,
            message="Export to Blender completed",
            blender_file_path=request.blend_file_path,
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.exception(f"Missing required files for export: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error exporting to Blender: {e}")
        raise HTTPException(status_code=500, detail=str(e))
