import logging

def suppress_noisy_package_logs():
    # Suppress some external loggers that are too verbose for our context/taste
    logging.getLogger("tzlocal").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.INFO)
    logging.getLogger("websocket").setLevel(logging.INFO)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("comtypes").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

