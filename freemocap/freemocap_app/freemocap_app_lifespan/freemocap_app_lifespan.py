import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import freemocap
from freemocap.api.server.server_constants import APP_URL
from freemocap.freemocap_app.freemocap_application import get_freemocap_app, FreemocapApplication
from freemocap.system.paths_and_filenames.path_getters import get_freemocap_data_folder_path

logger = logging.getLogger(__name__)


@asynccontextmanager
async def freemocap_application_lifespan(app: FastAPI):
    # Startup actions
    logger.api("FreeMoCap API starting...")
    logger.info(f"FreeMoCap API base folder path: {get_freemocap_data_folder_path()}")
    Path(get_freemocap_data_folder_path()).mkdir(parents=True, exist_ok=True)

    logger.info("Adding middleware...")
    freemocap_app:FreemocapApplication = get_freemocap_app()
    logger.success(f"FreeMoCap API (version:{freemocap.__version__}) started successfully 💀📸✨")
    logger.api(f"FreeMoCap API  running on: \n\t\tSwagger API docs - {APP_URL}")

    # # Let the app do its thing
    yield

    # Shutdown actions
    logger.api("FreeMoCap API ending...")
    freemocap_app.close()
    logger.success("FreeMoCap API shutdown complete - Goodbye!👋")
