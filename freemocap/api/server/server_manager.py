import logging
import multiprocessing
import threading
import time
from typing import Optional

import uvicorn
from uvicorn import Server

from freemocap.api.server.server_constants import HOSTNAME, PORT
from freemocap.app.app_lifespan.create_app import create_app
from freemocap.utilities.kill_process_on_port import kill_process_on_port

logger = logging.getLogger(__name__)


class UvicornServerManager:
    def __init__(self,
                 global_kill_flag: multiprocessing.Value,
                 hostname: str = HOSTNAME,
                 port: int = PORT,
                 log_level: str = "info"):
        self._global_kill_flag = global_kill_flag
        self.hostname: str = hostname
        self.port: int = port
        self.server_thread: Optional[threading.Thread] = None
        self.server: Optional[Server] = None
        self.log_level: str = log_level

    @property
    def is_running(self):
        return self.server_thread.is_alive() if self.server_thread else False

    def start_server(self):

        config = uvicorn.Config(
            create_app,
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
            try:
                self.server.run()
            except Exception as e:
                logger.error(f"A fatal error occurred in the uvicorn server: {e}")
                logger.exception(e)
                raise
            finally:
                logger.info(f"Shutting down uvicorn server")

        self.server_thread = threading.Thread(target=server_thread)
        self.server_thread.start()

    def shutdown_server(self):
        logger.info("Shutting down Uvicorn Server...")
        self._global_kill_flag.value = True
        if self.server:
            self.server.should_exit = True
            waiting_time = 0
            while self.server_thread.is_alive():
                waiting_time += 1
                time.sleep(1)
                if waiting_time > 10:
                    logger.debug("Server thread is not shutting down. Forcing exit...")
                    self.server.force_exit = True

            logger.info("Uvicorn Server shutdown successfully")
