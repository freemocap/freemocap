"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import asyncio
import logging
import multiprocessing
import os
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import skellycam
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import freemocap
from freemocap.api.http.app.health import health_router
from freemocap.api.http.app.shutdown import shutdown_router
from freemocap.api.middleware.add_middleware import add_middleware
from freemocap.api.middleware.cors import cors
from freemocap.api.routers import SKELLYCAM_ROUTERS, FREEMOCAP_ROUTERS
from freemocap.api.server_constants import APP_URL
from freemocap.api.websocket.websocket_connect import websocket_router
from freemocap.freemocap_app.freemocap_application import create_freemocap_app
from freemocap.system.default_paths import (
    get_default_freemocap_base_folder_path, FREEMOCAP_FAVICON_ICO_PATH
)
from freemocap.utilities.wait_functions import await_1s

logger = logging.getLogger(__name__)


async def monitor_kill_flag(app: FastAPI) -> None:
    """
    Background task to monitor the kill flag and trigger shutdown.
    """
    while not app.state.global_kill_flag.value:
        await await_1s()

    logger.info("Kill flag detected, initiating shutdown...")
    os.kill(os.getpid(), signal.SIGTERM)


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
    create_freemocap_app(global_kill_flag=app.state.global_kill_flag)
    # Start background task to monitor kill flag
    monitor_task = asyncio.create_task(monitor_kill_flag(app=app))

    logger.success(
        f"FreeMoCap API {freemocap.__version__} started successfully 💀✨\n"
        f"Swagger API docs: {APP_URL}/docs"
    )

    # Let the application do its thing
    yield

    # ===== SHUTDOWN =====
    logger.api("FreeMoCap API shutting down...")

    # Cancel the monitor task
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    # Cleanup FreeMoCap application
    app.state.global_kill_flag.value = True

    logger.success("FreeMoCap API shutdown complete - Goodbye! 👋")


def create_fastapi_app(global_kill_flag: multiprocessing.Value) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        global_kill_flag: Shared flag for coordinated shutdown

    Returns:
        Configured FastAPI application
    """
    # Create app with lifespan manager
    app = FastAPI(lifespan=app_lifespan)

    # Store dependencies in app state
    app.state.global_kill_flag = global_kill_flag

    # Configure CORS
    cors(app)

    # Register routes
    _register_routes(app)

    # Add middleware
    add_middleware(app)

    # Customize OpenAPI
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
    # Health and shutdown routes (no prefix)
    logger.api("\nRegistering App level routes:")
    for router in [health_router, shutdown_router]:
        app.include_router(router)
        for route in router.routes:
            logger.api(f"\tRegistered: {route.path} with methods: [{', '.join(route.methods)}]")

    logger.api("\nRegistering FreeMoCap endpoints:")
    for router in FREEMOCAP_ROUTERS:
        app.include_router(router, prefix=f"/{freemocap.__package_name__}")
        for route in router.routes:
            logger.api(f"\tRegistering route: `/{freemocap.__package_name__}{route.path}` with methods: [{', '.join(route.methods)}]")

    logger.api("\nRegistering SkellyCam endpoints:")
    for router in SKELLYCAM_ROUTERS:
        for route in router.routes:
            logger.api(f"\tRegistering route: `/{skellycam.__package_name__}{route.path}` with methods: [{', '.join(route.methods)}]")
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
