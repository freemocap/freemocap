import logging

import uvicorn

logger = logging.getLogger(__name__)

APP_FACTORY_IMPORT_STRING = "freemocap.api.app_factory:create_app"

def run_uvicorn_server(
        hostname: str,
        port: int,
):

    try:
        uvicorn.run(
            APP_FACTORY_IMPORT_STRING,
            host=hostname,
            port=port,
            log_level="info",
            reload=True,
            factory=True
        )
    except Exception as e:
        logger.error(f"A fatal error occurred in the uvicorn server: {e}")
        logger.exception(e)
        raise e
    finally:
        logger.info(f"Shutting down uvicorn server")


if __name__ == "__main__":
    run_uvicorn_server("localhost", 8003)