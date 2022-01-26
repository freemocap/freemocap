import uvicorn
from fastapi import FastAPI

from src.api.routes import enabled_routers


def create_app():
    app = FastAPI()

    for router in enabled_routers:
        app.include_router(router)

    return app


if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
