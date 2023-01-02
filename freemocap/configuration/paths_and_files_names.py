import logging
from pathlib import Path

import freemocap

logger = logging.getLogger(__name__)

# directory names
BASE_FREEMOCAP_DATA_FOLDER_NAME = "freemocap_data"
PATH_TO_FREEMOCAP_LOGO_SVG = str(
    Path(freemocap.__file__).parent.parent
    / "assets/logo/freemocap-logo-black-border.svg"
)


def os_independent_home_dir():
    return str(Path.home())


def get_freemocap_data_folder_path(create_folder: bool = True):
    freemocap_data_folder_path = Path(
        os_independent_home_dir(), BASE_FREEMOCAP_DATA_FOLDER_NAME
    )

    if create_folder:
        freemocap_data_folder_path.mkdir(exist_ok=create_folder, parents=True)

    return str(freemocap_data_folder_path)


def get_css_stylesheet_path():
    return str(
        Path(__file__).parent.parent / "qt_gui" / "style_sheet" / "qt_style_sheet.css"
    )
