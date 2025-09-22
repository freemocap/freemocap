import logging
import multiprocessing
import sys
import time

from freemocap.api.server.server_manager import UvicornServerManager
from freemocap.api.server.server_singleton import create_server_manager
from freemocap.utilities.setup_windows_app_id import setup_app_id_for_windows

logger = logging.getLogger(__name__)


def run_freemocap_server(global_kill_flag: multiprocessing.Value):
    server_manager:UvicornServerManager = create_server_manager(global_kill_flag=global_kill_flag)
    server_manager.run_server()
    while server_manager.is_running:
        time.sleep(1)
        if global_kill_flag.value:
            server_manager.shutdown_server()
            break

    logger.info("Server main process ended")


if __name__ == "__main__":

    multiprocessing.freeze_support()
    if sys.platform == "win32":
        setup_app_id_for_windows()
    outer_global_kill_flag = multiprocessing.Value("b", False)
    run_freemocap_server(outer_global_kill_flag)
    outer_global_kill_flag.value = True
    print("Done!")
