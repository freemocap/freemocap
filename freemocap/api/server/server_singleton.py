import multiprocessing
from typing import Optional

from freemocap.api.server.server_manager import UvicornServerManager

UVICORN_SERVER_MANAGER: Optional[UvicornServerManager] = None


def create_server_manager(global_kill_flag: multiprocessing.Value, *args, **kwargs) -> UvicornServerManager:
    global UVICORN_SERVER_MANAGER
    if UVICORN_SERVER_MANAGER is not None:
        raise Exception("Server manager already created, but you tried to create it again!")
    UVICORN_SERVER_MANAGER = UvicornServerManager(global_kill_flag, *args, **kwargs)
    return UVICORN_SERVER_MANAGER


def get_server_manager() -> UvicornServerManager:
    global UVICORN_SERVER_MANAGER
    if UVICORN_SERVER_MANAGER is None:
        raise Exception("Server manager not created yet!")
    return UVICORN_SERVER_MANAGER
