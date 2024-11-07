import logging
import multiprocessing
import sys
import threading
import time

from freemocap.run_freemocap_server import run_freemocap_server
from freemocap.system.paths_and_filenames.file_and_folder_names import SPARKLES_EMOJI_STRING, SKULL_EMOJI_STRING
from freemocap.utilities.clean_path import clean_path
from freemocap.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)


def main():
    logger.info(f"Running from __main__: {__name__} - {clean_path(__file__)}")
    if sys.platform == "win32":
        setup_app_id_for_windows()

    global_kill_flag = multiprocessing.Value('b', False)

    logger.info("Starting server...")
    server_thread = threading.Thread(run_freemocap_server(global_kill_flag), daemon=True)
    server_thread.start()

    while server_thread.is_alive():
        time.sleep(1)
        if global_kill_flag.value:
            break

    # server_process = multiprocessing.Process(target=run_freemocap_server, args=(global_kill_flag,))
    # logger.info("Starting backend server process")
    # server_process.start()
    # time.sleep(1)  # Give the backend time to startup
    #
    # logger.info("Starting frontend GUI")
    # freemocap_gui_main(global_kill_flag) # blocks until GUI is closed
    #
    # logger.info("Frontend GUI ended")
    global_kill_flag.value = True
    # server_process.join()
    logger.info("Exiting `main`...")


if __name__ == "__main__":
    multiprocessing.freeze_support()

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
