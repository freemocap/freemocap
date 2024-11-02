import logging
import multiprocessing
import time

from freemocap.api.server.server_singleton import create_server_manager

logger = logging.getLogger(__name__)


def run_server(global_kill_flag: multiprocessing.Value):
    server_manager = create_server_manager(global_kill_flag=global_kill_flag)
    server_manager.start_server()
    while server_manager.is_running:
        time.sleep(1)
        if global_kill_flag.value:
            server_manager.shutdown_server()
            break

    logger.info("Server main process ended")


if __name__ == "__main__":
    outer_global_kill_flag = multiprocessing.Value("b", False)
    run_server(outer_global_kill_flag)
    outer_global_kill_flag.value = True
    print("Done!")
