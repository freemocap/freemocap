import logging

import uvicorn
from fastapi import FastAPI

from src.api.middleware.cors import cors
from src.api.routes import enabled_routers

logger = logging.getLogger(__name__)


def create_app(*args, **kwargs):
    logger.info("Creating FastAPI app")
    _app = FastAPI()

    cors(_app)

    for router in enabled_routers:
        logger.info(f"Registering router {router}")
        _app.include_router(router)

    return _app


if __name__ == "__main__":
    logger.info("Running script app")
    host = "127.0.0.1"
    port = 8082
    logger.info(f"Running FastAPI server on {host}:{port}")
    uvicorn.run("app_factory:create_app",
                host=host,
                port=port,
                log_level="debug",
                reload=True,
                factory=True)
