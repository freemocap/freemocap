import logging
import multiprocessing
import threading
import time

import psutil
import uvicorn
from uvicorn import Server

from freemocap.api.server.server_constants import HOSTNAME, PORT
from freemocap.freemocap_app.freemocap_app_lifespan.freemocap_app_setup import create_freemocap_fastapi_app
from freemocap.freemocap_app.freemocap_application import  get_freemocap_app
from freemocap.utilities.kill_process_on_port import kill_process_on_port

logger = logging.getLogger(__name__)


class UvicornServerManager:
    def __init__(self,
                 global_kill_flag: multiprocessing.Value,
                 hostname: str = HOSTNAME,
                 port: int = PORT,
                 log_level: str = "info"):
        self._global_kill_flag = global_kill_flag
        get_freemocap_app()
        self.hostname: str = hostname
        self.port: int = port
        self.server_thread: threading.Thread|None = None
        self.server: Server|None = None
        self.log_level: str = log_level
        self.shutdown_listener_thread = threading.Thread(target=self.shutdown_listener_loop,
                                                         name="UvicornServerManagerShutdownListenerThread",
                                                         daemon=True)
        self.shutdown_listener_thread.start()


    @property
    def is_running(self):
        return self.server_thread.is_alive() if self.server_thread else False

    def run_server(self):

        config = uvicorn.Config(
            create_freemocap_fastapi_app,
            host=self.hostname,
            port=self.port,
            log_level=0,  # self.log_level,
            reload=True,
            factory=True
        )

        logger.info(f"Starting uvicorn server on {self.hostname}:{self.port}")
        kill_process_on_port(port=self.port)
        self.server = uvicorn.Server(config)

        def server_thread():
            logger.debug("Server thread started")
            try:
                logger.debug("Running uvicorn server...")
                self.server.run() #blocks until server is stopped
                logger.info("Running uvicorn server...")
            except Exception as e:
                logger.error(f"A fatal error occurred in the uvicorn server: {e}")
                logger.exception(e)
                raise
            finally:
                self._global_kill_flag.value = True
                logger.info(f"Uvicorn server thread completed")

        self.server_thread = threading.Thread(target=server_thread, name="UvicornServerManagerThread", daemon=True)
        self.server_thread.start()
        while not self._global_kill_flag.value and self.server_thread.is_alive():
            time.sleep(1)
        logger.debug("Server thread shutdown")
        # kill_process_on_port(port=self.port)

    def shutdown_server(self):
        logger.info("Shutting down Uvicorn Server...")
        self._global_kill_flag.value = True
        if self.server:
            self.server.should_exit = True
        time.sleep(1)
        try:
            # Kill child processes
            current_process = psutil.Process()
            for child in current_process.children(recursive=True):
                logger.warning(f"Killing child process: {child} - figure out how to make this shut down gracefully!")
                child.kill()
        except Exception as e:
            logger.exception(f"Error killing child processes: {e}")

    def shutdown_listener_loop(self):
        logger.info("Starting shutdown listener loop")
        while self._global_kill_flag.value is False :
            time.sleep(1)
        if self._global_kill_flag.value:
            logger.info("Detected global kill flag - shutting down server")
            self.shutdown_server()
        logger.info("Shutdown listener loop ended")
