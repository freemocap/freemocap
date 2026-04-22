import logging
from pathlib import Path

from freemocap.system.paths_and_filenames.file_and_folder_names import PATH_TO_FREEMOCAP_LOGO_SVG

logger = logging.getLogger(__name__)

_LOGO_DIR = Path(PATH_TO_FREEMOCAP_LOGO_SVG).parent
_ASSETS_DIR = _LOGO_DIR.parent

SKELLY_LOGO_BASE_SVG_FILENAME = "freemocap-logo-black-border.svg"

def _logo(filename: str) -> str:
    path = str(_LOGO_DIR / filename)
    if not Path(path).exists():
        logger.warning(f"Could not find {path}")
    return path

SKELLY_SWEAT_PNG = _logo("skelly-sweat.png")
SKELLY_HEART_EYES_PNG = _logo("skelly-heart-eyes.png")
SKELLY_THIS_WAY_UP_PNG = _logo("skelly-this-way-up.png")
SKELLY_OUTLIER_REJECTION = _logo("skelly-outlier-rejection.png")

CHARUCO_AS_GROUND_PLANE_PNG = str(_ASSETS_DIR / "charuco/charuco_as_groundplane.png")
OUTLIER_REJECTION_UI_PNG = str(_ASSETS_DIR / "release-notes/outlier_rejection_ui.png")

for _p in [CHARUCO_AS_GROUND_PLANE_PNG, OUTLIER_REJECTION_UI_PNG]:
    if not Path(_p).exists():
        logger.warning(f"Could not find {_p}")
