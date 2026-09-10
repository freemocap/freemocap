"""Propagate application failures to the server's shutdown and exit status."""

import asyncio

from fastapi import FastAPI
from uvicorn import Server


async def _serve(*, server: Server, app: FastAPI) -> None:
    try:
        await server.serve()
    except SystemExit as error:
        # Uvicorn exits on startup failure; keep it inside the supervised task.
        if app.state.fatal_error is not None:
            raise RuntimeError("Server stopped after a fatal application error") from app.state.fatal_error
        raise RuntimeError(f"Server exited with status {error.code}") from error


async def serve_application(*, server: Server, app: FastAPI) -> None:
    server_task = asyncio.create_task(_serve(server=server, app=app), name="FreeMoCapServer")
    try:
        while not server_task.done():
            if app.state.global_kill_flag.value:
                server.should_exit = True
            await asyncio.sleep(0.1)
        await server_task
        if app.state.fatal_error is not None:
            raise RuntimeError("Server stopped after a fatal application error") from app.state.fatal_error
        if not server.started:
            raise RuntimeError("Server startup failed; see the startup traceback")
    finally:
        if not server_task.done():
            server.should_exit = True
            await server_task
