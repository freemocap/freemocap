import asyncio
import logging
import multiprocessing
import os
import signal
import sys
from threading import Event

from freemocap.app.serve_application import serve_application

# Ensure sys.stdout/sys.stderr are valid — PyInstaller frozen subprocesses
# may set them to None, which breaks libraries like tqdm that write to stderr.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

logger = logging.getLogger(__name__)


async def main(force_preferred_port:bool=True) -> None:
    # Configure logging once, at startup — NOT at import time. freemocap's
    # package __init__ stays side-effect free so sandboxes/CI/child processes
    # can import it without I/O or thread spawns.
    from skellylogs import configure_logging, LogLevels
    configure_logging(LogLevels.TRACE)

    from skellylogs import get_websocket_log_queue
    from freemocap.api.websocket.log_relay import LogRelay
    log_relay = LogRelay(get_websocket_log_queue())
    log_relay.start()
    producers_stopped = Event()
    producers_stopped.set()
    try:
        await _run_application(force_preferred_port, log_relay, producers_stopped)
    finally:
        if producers_stopped.is_set():
            log_relay.stop()
        else:
            # A failed worker shutdown must not remove its remaining log consumer.
            logger.error("Worker shutdown incomplete; log reader remains active until process exit")


async def _run_application(force_preferred_port, log_relay, producers_stopped) -> None:
    # Heavy imports are here (not at module level) so that multiprocessing
    # child processes don't re-import the entire app tree on Windows.
    # Windows uses the `spawn` start method, which re-executes this file
    # in every child process — but only `main()` needs these imports,
    # and children never call `main()`.
    import uvicorn
    from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
    from skellycam.core.ipc.process_management.managed_worker import WorkerMode
    from skellycam.utilities.kill_process_on_port import kill_process_on_port
    from skellycam.utilities.wait_functions import await_1s

    from freemocap.api.server_constants import (
        HOSTNAME,
        find_available_port,
        PREFERRED_PORT,
        format_port_sentinel,
    )
    from freemocap.app.app import create_fastapi_app
    from freemocap.api.websocket.closing_aware_protocol import ClosingAwareWebSocketProtocol
    from freemocap.utilities.asyncio_exception_handler import suppress_proactor_connection_reset


    if force_preferred_port:
        port = PREFERRED_PORT
        kill_process_on_port(port=port)
    else:
        port = find_available_port()
    # Print the port sentinel to stdout so the Electron main process can discover it.
    # flush=True ensures it arrives immediately even when stdout is buffered.
    print(format_port_sentinel(port=port), flush=True)

    suppress_proactor_connection_reset(asyncio.get_running_loop())

    global_kill_flag = multiprocessing.Value("b", False)
    worker_registry = WorkerRegistry(
        global_kill_flag=global_kill_flag,
        worker_mode=WorkerMode.PROCESS
    )

    server: uvicorn.Server | None = None
    signum_to_signal_name = {
        signal.SIGINT: "signal.SIGINT",
        signal.SIGTERM: "signal.SIGTERM",
    }

    def handle_signal(signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}({signum_to_signal_name[signum]}), initiating shutdown...")
        global_kill_flag.value = True
        if server:
            server.should_exit = True

    for sigint, signal_name in signum_to_signal_name.items():
        logger.trace(f"Registering shutdown signal {sigint}: ({signum_to_signal_name[sigint]})")
        signal.signal(sigint, handle_signal)

    try:
        producers_stopped.clear()
        worker_registry.start_heartbeat()
        kill_process_on_port(port=port)

        app = create_fastapi_app(
            global_kill_flag=global_kill_flag,
            worker_registry=worker_registry,
            port=port,
        )

        app.state.log_relay = log_relay

        config = uvicorn.Config(
            app=app,
            host=HOSTNAME,
            port=port,
            log_level="warning",
            ws=ClosingAwareWebSocketProtocol,
            reload=False,
        )
        server = uvicorn.Server(config)

        logger.info(f"Starting server on {HOSTNAME}:{port}")
        await serve_application(server=server, app=app)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        global_kill_flag.value = True
        try:
            if server:
                server.should_exit = True
                await await_1s()
        finally:
            worker_registry.shutdown_all()
            producers_stopped.set()
            logger.info("FreeMoCap workers shut down")

def run_main() -> None:
    asyncio.run(main())
if __name__ == "__main__":
    multiprocessing.freeze_support()  # Required for PyInstaller + multiprocessing on Windows
    try:
        run_main()
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        os._exit(1)
    print("Done!")
    os._exit(0)
