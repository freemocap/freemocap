import logging
from pathlib import Path

import freemocap

logger = logging.getLogger(__name__)

# directory names
BASE_FREEMOCAP_DATA_FOLDER_NAME = "freemocap_data"
RECORDING_SESSIONS_FOLDER_NAME = "recording_sessions"
CALIBRATIONS_FOLDER_NAME = "calibrations"
LOGS_INFO_AND_SETTINGS_FOLDER_NAME = "logs_info_and_settings"
LOG_FILE_FOLDER_NAME = "logs"
OUTPUT_DATA_FOLDER_NAME = "output_data"
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
ANNOTATED_VIDEOS_FOLDER_NAME = "annotated_videos"
RAW_DATA_FOLDER_NAME = "raw_data"
CENTER_OF_MASS_FOLDER_NAME = "center_of_mass"

# file names
MOST_RECENT_RECORDING_TOML_FILENAME = "most_recent_recording.toml"
LAST_SUCCESSFUL_CALIBRATION_TOML_FILENAME = "last_successful_calibration.toml"
MEDIAPIPE_2D_NPY_FILE_NAME = "mediapipe2dData_numCams_numFrames_numTrackedPoints_pixelXY.npy"
MEDIAPIPE_BODY_WORLD_FILE_NAME = "mediapipeBodyWorld_numCams_numFrames_numTrackedPoints_XYZ.npy"
MEDIAPIPE_3D_NPY_FILE_NAME = "mediaPipeSkel_3d_body_hands_face.npy"
RAW_MEDIAPIPE_3D_NPY_FILE_NAME = "mediapipe3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
MEDIAPIPE_REPROJECTION_ERROR_NPY_FILE_NAME = "mediapipe3dData_numFrames_numTrackedPoints_reprojectionError.npy"
MEDIAPIPE_BODY_3D_DATAFRAME_CSV_FILE_NAME = "mediapipe_body_3d_xyz.csv"

SEGMENT_CENTER_OF_MASS_NPY_FILE_NAME = "segmentCOM_frame_joint_xyz.npy"

TOTAL_BODY_CENTER_OF_MASS_NPY_FILE_NAME = "total_body_center_of_mass_xyz.npy"

# Figshare info
FIGSHARE_ZIP_FILE_URL = "https://figshare.com/ndownloader/files/40293973"
FIGSHARE_SAMPLE_DATA_FILE_NAME = "freemocap_sample_data"

# logo
PATH_TO_FREEMOCAP_LOGO_SVG = str(Path(freemocap.__file__).parent.parent / "assets/logo/freemocap-logo-black-border.svg")

# emoji strings
SPARKLES_EMOJI_STRING = "\U00002728"
DIZZY_EMOJI_STRING = "\U0001F4AB"
EYES_EMOJI_STRING = "\U0001F440"
SKULL_EMOJI_STRING = "\U0001F480"
CAMERA_WITH_FLASH_EMOJI_STRING = "\U0001F4F8"
HAMMER_AND_WRENCH_EMOJI_STRING = "\U0001F6E0"
ROBOT_EMOJI_STRING = "\U0001F916"
THREE_HEARTS_EMOJI_STRING = "\U0001F495"
WIND_EMOJI_STRING = "\U0001F32C"
GEAR_EMOJI_STRING = "\U00002699"
FOLDER_EMOJI_STRING = "\U0001F4C1"
DIRECTORY_EMOJI_STRING = "\U0001F4C1"
COOL_EMOJI_STRING = "\U0001F60E"


