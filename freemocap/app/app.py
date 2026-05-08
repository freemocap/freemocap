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


# ── GPU hardware detection ───────────────────────────────────────────────


def _query_nvidia_smi() -> list[dict]:
    """Query NVIDIA GPUs via nvidia-smi.

    Returns a list of dicts with keys: name, vram_gb, driver_version, compute_capability.
    Returns an empty list if nvidia-smi is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,driver_version,compute_cap",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        # Retry without compute_cap for older nvidia-smi versions
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total,driver_version",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    gpus: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",", maxsplit=3)]
        # memory.total comes back as e.g. "24576 MiB" — strip the unit
        vram_mib = 0.0
        if len(parts) > 1 and parts[1]:
            vram_str = parts[1].replace("MiB", "").replace(" ", "").strip()
            try:
                vram_mib = float(vram_str)
            except ValueError:
                vram_mib = 0.0
        gpu: dict = {
            "name": parts[0] if parts[0] else "Unknown NVIDIA GPU",
            "vram_gb": f"{vram_mib / 1024:.1f} GB" if vram_mib > 0 else None,
            "driver_version": parts[2] if len(parts) > 2 and parts[2] else None,
            "compute_capability": parts[3] if len(parts) > 3 and parts[3] else None,
        }
        gpus.append(gpu)
    return gpus


def _query_wmic_gpus() -> list[dict]:
    """Fallback GPU detection on Windows via WMIC."""
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_videocontroller",
             "get", "name,adapterram",
             "/format:csv"],
            capture_output=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    # WMIC outputs UTF-16LE with BOM; decode explicitly
    stdout = result.stdout.decode("utf-16-le", errors="replace")

    gpus: list[dict] = []
    for line in stdout.strip().splitlines():
        if not line.strip() or "Node," in line:
            continue
        # WMIC CSV column order is: Node,AdapterRAM,Name
        parts = [p.strip() for p in line.split(",", maxsplit=2)]
        if len(parts) < 3 or not parts[2]:
            continue
        name = parts[2]
        vram_bytes = int(parts[1]) if parts[1].isdigit() else 0
        gpu: dict = {
            "name": name,
            "vram_gb": f"{vram_bytes / 1e9:.1f} GB" if vram_bytes > 0 else None,
            "driver_version": None,
            "compute_capability": None,
        }
        gpus.append(gpu)
    return gpus


def _query_lspci_gpus() -> list[dict]:
    """Fallback GPU detection on Linux via lspci."""
    try:
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    gpus: list[dict] = []
    for line in result.stdout.strip().splitlines():
        if not any(tag in line for tag in ("VGA", "3D", "Display")):
            continue
        # lspci format: "00:02.0 VGA compatible controller: Intel Corporation ..."
        name = line.split(":", 2)[-1].strip() if ":" in line else line.strip()
        gpu: dict = {
            "name": name,
            "vram_gb": None,
            "driver_version": None,
            "compute_capability": None,
        }
        gpus.append(gpu)
    return gpus


def _query_macos_gpus() -> list[dict]:
    """Fallback GPU detection on macOS via system_profiler."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    gpus: list[dict] = []
    current: dict | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Chipset Model:"):
            if current is not None:
                gpus.append(current)
            current = {"name": stripped.split(":", 1)[1].strip(),
                        "vram_gb": None, "driver_version": None, "compute_capability": None}
        elif current is not None and stripped.startswith("VRAM"):
            vram_str = stripped.split(":", 1)[1].strip()
            # Normalize: "8 GB" or "8192 MB" → "8.0 GB"
            current["vram_gb"] = vram_str
        elif current is not None and stripped.startswith("Metal:"):
            current["metal"] = stripped.split(":", 1)[1].strip()
    if current is not None:
        gpus.append(current)
    return gpus


def _detect_gpus() -> list[dict]:
    """Detect GPU hardware, trying multiple strategies in priority order."""
    gpus = _query_nvidia_smi()
    if gpus:
        return gpus

    system = platform.system()
    if system == "Windows":
        return _query_wmic_gpus()
    elif system == "Linux":
        return _query_lspci_gpus()
    elif system == "Darwin":
        return _query_macos_gpus()

    return []


def _format_gpu_section(gpus: list[dict]) -> str:
    """Format the GPU hardware section for log output."""
    if not gpus:
        return "    GPU:                       None detected"

    lines: list[str] = ["    GPU:"]
    for i, gpu in enumerate(gpus):
        lines.append(f"      GPU {i}: {gpu['name']}")
        if gpu.get("vram_gb"):
            lines.append(f"        VRAM:                {gpu['vram_gb']}")
        if gpu.get("driver_version"):
            lines.append(f"        Driver Version:      {gpu['driver_version']}")
        if gpu.get("compute_capability"):
            lines.append(f"        Compute Capability:  {gpu['compute_capability']}")
    return "\n".join(lines)


# ── ONNX Runtime detection ───────────────────────────────────────────────


def _get_onnx_info() -> tuple[str | None, list[str]]:
    """Get ONNX Runtime version and available execution providers."""
    try:
        import onnxruntime  # noqa: TC002
    except Exception:
        return None, []
    try:
        return onnxruntime.__version__, onnxruntime.get_available_providers()
    except Exception:
        return None, []


def _format_onnx_section(version: str | None, providers: list[str], gpus: list[dict]) -> str:
    """Format the ONNX Runtime section for log output."""
    lines: list[str] = ["    ONNX Runtime:"]

    if version:
        lines.append(f"      Version:   {version}")
    else:
        lines.append("      Version:   Not installed")

    if providers:
        lines.append(f"      Providers: {', '.join(providers)}")

    # GPU acceleration capability summary
    has_cuda = any("CUDA" in p for p in providers)
    has_trt = any("Tensorrt" in p for p in providers)
    has_gpu_hw = bool(gpus)

    if has_cuda:
        lines.append(f"      GPU acceleration:       Available (CUDAExecutionProvider)")
    elif has_trt:
        lines.append(f"      GPU acceleration:       Available (TensorrtExecutionProvider)")
    elif has_gpu_hw:
        if not version:
            lines.append("      GPU acceleration:       Not available — ONNX Runtime not installed")
        else:
            lines.append("      GPU acceleration:       Not available — onnxruntime-gpu may not be installed")
    else:
        lines.append("      GPU acceleration:       Not available — no GPU detected")

    return "\n".join(lines)


# ── Main system info logger ──────────────────────────────────────────────


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

    skelly_pkg_str = "\n".join(f"      {k}={v}" for k, v in skelly_pkgs.items())

    vm = psutil.virtual_memory()
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    try:
        cpu_freq_ghz = f"{psutil.cpu_freq().current / 1000:.2f} GHz"
    except Exception:
        cpu_freq_ghz = "unknown"

    gpus = _detect_gpus()
    onnx_version, onnx_providers = _get_onnx_info()

    gpu_section = _format_gpu_section(gpus)
    onnx_section = _format_onnx_section(onnx_version, onnx_providers, gpus)

    logger.info(
        f"\n"
        f"  System info:\n"
        f"    OS:          {platform.system()} {platform.release()} ({platform.version()})\n"
        f"    CPU:         {platform.processor()} -- {cpu_physical} physical / {cpu_logical} logical cores @ {cpu_freq_ghz}\n"
        f"    RAM:         {vm.total / 1e9:.1f} GB total, {vm.available / 1e9:.1f} GB available\n"
        f"    Python:      {sys.version}\n"
        f"    FreeMoCap:   {freemocap.__version__}\n"
        f"\n"
        f"{gpu_section}\n"
        f"\n"
        f"{onnx_section}\n"
        f"\n"
        f"    Skelly Packages:\n"
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
