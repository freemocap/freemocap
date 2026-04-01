"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import asyncio
import logging
import multiprocessing
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import skellycam
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from starlette.responses import FileResponse

import freemocap
from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import shutdown_router
from freemocap.api.http.app.state import state_router
from freemocap.api.middleware.add_middleware import add_middleware
from freemocap.api.middleware.cors import cors
from freemocap.api.routers import SKELLYCAM_ROUTERS, FREEMOCAP_ROUTERS, APP_ROUTERS
from freemocap.api.server_constants import PROTOCOL, HOSTNAME
from freemocap.api.udp.vmc_relay import vmc_relay_task
from freemocap.api.websocket.websocket_connect import websocket_router
from freemocap.app.freemocap_application import create_freemocap_app, get_freemocap_app
from freemocap.system.default_paths import (
    get_default_freemocap_base_folder_path, FREEMOCAP_FAVICON_ICO_PATH
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(
        app: FastAPI
) -> AsyncGenerator[None, None]:
    """
    Manage the application lifecycle.
    All startup and shutdown logic goes here.
    """
    # ===== STARTUP =====
    logger.api("FreeMoCap API starting...")

    # Ensure base folder exists
    base_path = Path(get_default_freemocap_base_folder_path())
    base_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Base folder: {base_path}")

    app_url = f"{PROTOCOL}://{HOSTNAME}:{app.state.port}"

    logger.success(
        f"FreeMoCap API {freemocap.__version__} started successfully 💀✨\n"
        f"Swagger API docs: {app_url}/docs"
    )

    yield

    # ===== SHUTDOWN =====
    logger.api("FreeMoCap API shutting down...")

    app.state.global_kill_flag.value = True

    logger.success("FreeMoCap API shutdown complete - Goodbye! 👋")


def create_fastapi_app(
        *,
        global_kill_flag: multiprocessing.Value,
        worker_registry: WorkerRegistry,
        port: int,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(lifespan=app_lifespan)

    app.state.global_kill_flag = global_kill_flag
    app.state.worker_registry = worker_registry
    app.state.port = port
    create_freemocap_app(fastapi_app=app)
    cors(app)
    _register_routes(app)
    add_middleware(app)
    _customize_openapi(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all application routes."""

    # Root redirect
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse("/docs")

    # Favicon
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(FREEMOCAP_FAVICON_ICO_PATH)

    logger.api(f"\nRegistering WebSocket routes:")
    app.include_router(websocket_router)
    for route in websocket_router.routes:
        logger.api(f"\tRegistered WebSocket route: {route.path}")

    # Health, shutdown, and settings state routes (no prefix)
    logger.api("\nRegistering App level routes:")
    for router in APP_ROUTERS:
        app.include_router(router)
        for route in router.routes:
            logger.api(f"\tRegistered: {route.path} with methods: [{', '.join(route.methods)}]")

    logger.api("\nRegistering FreeMoCap endpoints:")
    for router in FREEMOCAP_ROUTERS:
        app.include_router(router, prefix=f"/{freemocap.__package_name__}")
        for route in router.routes:
            logger.api(
                f"\tRegistering route: `/{freemocap.__package_name__}{route.path}` with methods: [{', '.join(route.methods)}]")

    logger.api("\nRegistering FreeMoCap endpoints:")
    for router in SKELLYCAM_ROUTERS:
        for route in router.routes:
            logger.api(
                f"\tRegistering route: `/{skellycam.__package_name__}{route.path}` with methods: [{', '.join(route.methods)}]")
        app.include_router(router, prefix=f"/{skellycam.__package_name__}")


def _customize_openapi(app: FastAPI) -> None:
    """Customize the OpenAPI schema."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="FreeMoCap API 💀✨",
            version=freemocap.__version__,
            description=(
                f"FastAPI Backend for FreeMoCap: {freemocap.__description__}"
            ),
            routes=app.routes,
        )

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
