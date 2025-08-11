import logging
import multiprocessing
import sys

import freemocap
from freemocap.freemocap_app.freemocap_application import create_freemocap_app, get_freemocap_app
from freemocap.run_freemocap_server import run_freemocap_server
from freemocap.system.paths_and_filenames.file_and_folder_names import SPARKLES_EMOJI_STRING, SKULL_EMOJI_STRING
from freemocap.utilities.clean_path import clean_path
from freemocap.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)

logger.debug(
    f"Initializing {freemocap.__package_name__} package, version: {freemocap.__version__}, from file: {__file__}")


def main():
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")

    global_kill_flag = multiprocessing.Value('b', False)
    create_freemocap_app(global_kill_flag=global_kill_flag)

    logger.info("Starting server...")
    run_freemocap_server(global_kill_flag)

    global_kill_flag.value = True
    get_freemocap_app().close()

    logger.info("Exiting `main`...")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if sys.platform == "win32":
        setup_app_id_for_windows()
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt - shutting down!")
    except Exception as e:
        logger.exception("An unexpected error occurred", exc_info=e)
        raise
    print("\n\n--------------------------------------------------\n--------------------------------------------------")
    print(f"Thank you for using FreeMoCap {SKULL_EMOJI_STRING} {SPARKLES_EMOJI_STRING}")
    print("--------------------------------------------------\n--------------------------------------------------\n\n")
