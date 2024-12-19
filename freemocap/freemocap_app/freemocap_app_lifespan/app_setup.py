import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import freemocap
from freemocap.api.routers import FREEMOCAP_ROUTERS

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    # @app.get('/favicon.ico', include_in_schema=False)
    # async def favicon():
    #     return FileResponse(SKELLYCAM_FAVICON_ICO_PATH)

    for prefix, routers in FREEMOCAP_ROUTERS.items():
        for name, router in routers.items():
            logger.api(f"Registering route: `{prefix}/{name}`")
            app.include_router(router, prefix=prefix)


def customize_swagger_ui(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Welcome to the FreeMoCap API 💀📸✨",
            version=freemocap.__version__,
            description=f"The FastAPI/Uvicorn/Swagger Backend UI for FreeMoCap: {freemocap.__description__}",
            routes=app.routes,
        )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
