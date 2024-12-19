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
    logger.api(f"FreeMoCap API starting (app: {app})...")
    logger.info(f"FreeMoCap API base folder path: {get_freemocap_data_folder_path()}")
    Path(get_freemocap_data_folder_path()).mkdir(parents=True, exist_ok=True)


    logger.success(f"FreeMoCap API (version:{freemocap.__version__}) started successfully 💀📸✨")
    logger.api(f"FreeMoCap API  running on: \n\t\t\tSwagger API docs - {APP_URL} \n\t\t\tTest UI: {APP_URL}/ui 👈[click to open backend UI in your browser]")

    # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("FreeMoCap API ending...")
    logger.success("FreeMoCap API shutdown complete - Goodbye!👋")
