import asyncio
import logging
import multiprocessing
import signal
import sys

import uvicorn
from skellycam.utilities.kill_process_on_port import kill_process_on_port
from skellycam.utilities.wait_functions import await_1s

from freemocap.api.server_constants import HOSTNAME, PORT
from freemocap.app.app import create_fastapi_app

logger = logging.getLogger(__name__)


async def main() -> None:
    # Create shared kill flag for subprocesses
    global_kill_flag:multiprocessing.Value = multiprocessing.Value("b", False)
    subprocess_registry: list[multiprocessing.Process] = []
    server: uvicorn.Server | None = None

    def handle_signal(signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        global_kill_flag.value = True
        if server:
            server.should_exit = True

    # Setup signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        # Clean up any existing process on the port
        kill_process_on_port(port=PORT)

        # Create FastAPI app
        app = create_fastapi_app(global_kill_flag=global_kill_flag,
                                        subprocess_registry=subprocess_registry)

        # Configure and create Uvicorn server
        config = uvicorn.Config(
            app=app,
            host=HOSTNAME,
            port=PORT,
            log_level="warning",
            reload=False

        )
        server = uvicorn.Server(config)

        logger.info(f"Starting server on {HOSTNAME}:{PORT}")

        # Run server (blocks until shutdown)
        await server.serve()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Ensure kill flag is set and server is stopped
        global_kill_flag.value = True
        if server:
            server.should_exit = True
            await await_1s()  # Give it time to shut down gracefully

        for process in subprocess_registry:
            if process.is_alive():
                logger.info(f"Terminating subprocess {process.name} (PID: {process.pid})")
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    logger.warning(f"Force killing subprocess {process.name} (PID: {process.pid})")
                    process.kill()
                    process.join()
        logger.success("Done! Thank you for using SkellyCam 💀📸✨")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)
    else:
        sys.exit(0)