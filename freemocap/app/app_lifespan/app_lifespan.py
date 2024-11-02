import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import freemocap
from freemocap.api.server.server_constants import APP_URL
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.api("Skellycam API starting...")
    logger.info(f"Skellycam API base folder path: {get_freemocap_data_folder_path()}")
    Path(get_freemocap_data_folder_path()).mkdir(parents=True, exist_ok=True)

    logger.info("Adding middleware...")

    logger.info(f"Creating `Controller` instance...")
    logger.success(f"Skellycam API (version:{freemocap.__version__}) started successfully 💀📸✨")
    logger.api(f"Skellycam API  running on: \nSwagger API docs - {APP_URL} \n Test UI: test ui: {APP_URL}/ui 👈[click to open backend UI in your browser]\n")

    # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("Skellycam API ending...")
    logger.success("Skellycam API shutdown complete - Goodbye!👋")
