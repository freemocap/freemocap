import uvicorn
from fastapi import FastAPI

from src.api.middleware.cors import cors
from src.api.routes import enabled_routers


def create_app(*args, **kwargs):
    _app = FastAPI()

    cors(_app)

    for router in enabled_routers:
        _app.include_router(router)

    return _app


if __name__ == "__main__":
    script_app = create_app()
    uvicorn.run(script_app, host="127.0.0.1", port=8080, log_level="info")
