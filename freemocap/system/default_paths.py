import time
from datetime import datetime
from pathlib import Path

DEFAULT_FREEMOCAP_BASE_FOLDER_NAME = "freemocap_data"
SYNCHRONIZED_VIDEOS_FOLDER_NAME = "synchronized_videos"
LOGS_INFO_AND_SETTINGS_FOLDER_NAME = "logs_info_and_settings"
LOG_FILE_FOLDER_NAME = "logs"
TIMESTAMPS_FOLDER_NAME = "timestamps"

# Emoji strings
RED_X_EMOJI_STRING = "\U0000274C"
DIZZY_EMOJI_STRING = "\U0001F4AB"
SPARKLES_EMOJI_STRING = "\U00002728"
MAGNIFYING_GLASS_EMOJI_STRING = "\U0001F50D"
CAMERA_WITH_FLASH_EMOJI_STRING = "\U0001F4F8"
HAMMER_AND_WRENCH_EMOJI_STRING = "\U0001F6E0"
CLOCKWISE_VERTICAL_ARROWS_EMOJI_STRING = "\U0001F503"

SESSION_START_TIME_FORMAT_STRING = "ISO6201 format timestamp with GMT offset in hours"

FREEMOCAP_SVG_PATH = str(
    Path(__file__).parent.parent.parent / "shared" / "freemocap-logo" / "freemocap-logo.svg")
FREEMOCAP_FAVICON_ICO_PATH = str(
    Path(__file__).parent.parent.parent / "shared" / "freemocap-logo" / "freemocap-favicon.ico")


def os_independent_home_dir() -> str:
    return str(Path.home())


def get_default_freemocap_base_folder_path() -> str:
    return str(Path(os_independent_home_dir()) / DEFAULT_FREEMOCAP_BASE_FOLDER_NAME)


def get_default_freemocap_recordings_path() -> str:
    return str(Path(get_default_freemocap_base_folder_path()) / "recordings")


def get_default_recording_folder_path(tag: str = "") -> str:
    return str(Path(get_default_freemocap_base_folder_path()) / "recordings" / default_recording_name(string_tag=tag))


def get_log_file_path() -> str:
    log_folder_path = (
            Path(get_default_freemocap_base_folder_path()) / LOGS_INFO_AND_SETTINGS_FOLDER_NAME / LOG_FILE_FOLDER_NAME
    )
    log_folder_path.mkdir(exist_ok=True, parents=True)
    log_file_path = log_folder_path / create_log_file_name()
    return str(log_file_path)


def get_gmt_offset_string() -> str:
    # from - https://stackoverflow.com/a/53860920/14662833
    gmt_offset_int = int(time.localtime().tm_gmtoff / 60 / 60)
    return f"{gmt_offset_int:+}"


def create_log_file_name() -> str:
    return "log_" + get_iso6201_time_string() + ".log"


def get_iso6201_time_string(timespec: str = "milliseconds", make_filename_friendly: bool = True) -> str:
    iso6201_timestamp = datetime.now().isoformat(timespec=timespec)
    gmt_offset_string = f"_gmt{get_gmt_offset_string()}"
    iso6201_timestamp_w_gmt = iso6201_timestamp + gmt_offset_string
    if make_filename_friendly:
        iso6201_timestamp_w_gmt = iso6201_timestamp_w_gmt.replace(":", "_")
        iso6201_timestamp_w_gmt = iso6201_timestamp_w_gmt.replace(".", "ms")
    return iso6201_timestamp_w_gmt


def default_recording_name(string_tag: str = "") -> str:
    if len(string_tag) > 0:
        string_tag = f"_{string_tag}"
    else:
        string_tag = ""

    return time.strftime(get_iso6201_time_string(timespec="seconds") + string_tag)
