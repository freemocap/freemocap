"""
Consolidated FastAPI app factory with proper lifecycle management.
"""
import logging
import multiprocessing
import platform
import subprocess
import sys
from contextlib import asynccontextmanager
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from typing import AsyncGenerator

import psutil
import skellycam
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from starlette.responses import FileResponse

import freemocap
from freemocap.api.middleware.add_middleware import add_middleware
from freemocap.api.middleware.cors import cors
from freemocap.api.routers import SKELLYCAM_ROUTERS, FREEMOCAP_ROUTERS, APP_ROUTERS
from freemocap.api.server_constants import PROTOCOL, HOSTNAME
from freemocap.api.websocket.websocket_connect import websocket_router
from freemocap.app.freemocap_application import create_freemocap_app
from freemocap.system.default_paths import (
    get_default_freemocap_base_folder_path, FREEMOCAP_FAVICON_ICO_PATH
)

logger = logging.getLogger(__name__)


def _log_system_info() -> None:
    def _pkg_ver(name: str) -> str:
        try:
            mod = __import__(name)
            return mod.__version__
        except Exception:
            return "n/a"

    skelly_pkgs = {
        "skellycam": _pkg_ver("skellycam"),
        "skellytracker": _pkg_ver("skellytracker"),
        "skellyforge": _pkg_ver("skellyforge"),
        "skellylogs": _pkg_ver("skellylogs"),
        "skellypings": _pkg_ver("skellypings"),
        "freemocap_blender_addon": _pkg_ver("freemocap_blender_addon"),
    }

    skelly_pkg_str = "\n".join(f"\t\t\t\t\t{k}={v}" for k, v in skelly_pkgs.items())

    vm = psutil.virtual_memory()
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    try:
        cpu_freq_ghz = f"{psutil.cpu_freq().current / 1000:.2f} GHz"
    except Exception:
        cpu_freq_ghz = "unknown"

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheaders,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            gpu_lines = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
            gpu_info = " | ".join(f"GPU{i}: {ln}" for i, ln in enumerate(gpu_lines)) if gpu_lines else "none detected"
        else:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    except Exception:
        try:
            import onnxruntime as ort
            gpu_info = f"ORT providers: {ort.get_available_providers()}"
        except Exception:
            gpu_info = "unavailable"

    logger.info(
        f"\n"
        f"  System info:\n"
        f"    OS:          {platform.system()} {platform.release()} ({platform.version()})\n"
        f"    CPU:         {platform.processor()} — {cpu_physical} physical / {cpu_logical} logical cores @ {cpu_freq_ghz}\n"
        f"    RAM:         {vm.total / 1e9:.1f} GB total, {vm.available / 1e9:.1f} GB available\n"
        f"    GPU:         {gpu_info}\n"
        f"    Python:      {sys.version}\n"
        f"    FreeMoCap:   {freemocap.__version__}\n"
        f"    Skelly Pkgs:\n"
        f"{skelly_pkg_str}"
    )


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
    _log_system_info()

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
        global_kill_flag: Synchronized,
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

    logger.api("\nRegistering SkellyCam endpoints:")
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
