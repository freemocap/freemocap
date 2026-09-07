"""Native playback endpoint used by the Electron controller integration test."""

import multiprocessing
import socket
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.api.websocket.playback_socket import playback_socket_router


def main() -> None:
    app = FastAPI()
    app.state.worker_registry = WorkerRegistry(
        global_kill_flag=multiprocessing.Value("b", False), worker_mode=WorkerMode.THREAD)
    app.include_router(playback_socket_router)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        Path(sys.argv[1]).write_text(str(listener.getsockname()[1]), encoding="utf-8")
        uvicorn.Server(uvicorn.Config(app=app, log_level="error")).run(sockets=[listener])


if __name__ == "__main__":
    main()
