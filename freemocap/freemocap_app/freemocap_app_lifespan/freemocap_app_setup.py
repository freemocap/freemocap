import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from starlette.responses import FileResponse

import skellycam

import freemocap
from freemocap.api.routers import SKELLYCAM_ROUTERS, FREEMOCAP_ROUTERS
from skellycam.system.default_paths import SKELLYCAM_FAVICON_ICO_PATH

from freemocap.api.middleware.add_middleware import add_middleware
from freemocap.api.middleware.cors import cors
from freemocap.freemocap_app.freemocap_app_lifespan.freemocap_app_lifespan import freemocap_application_lifespan

logger = logging.getLogger(__name__)

def create_freemocap_fastapi_app() -> FastAPI:
    logger.api("Creating FastAPI app")
    app = FastAPI(lifespan=freemocap_application_lifespan)
    cors(app)
    register_routes(app)
    add_middleware(app)
    customize_swagger_ui(app)
    return app

def register_routes(app: FastAPI):
    @app.get("/")
    async def read_root():
        return RedirectResponse("/docs")

    @app.get('/favicon.ico', include_in_schema=False)
    async def favicon():
        return FileResponse(SKELLYCAM_FAVICON_ICO_PATH)

    for router in FREEMOCAP_ROUTERS:
        app.include_router(router)
    for router in SKELLYCAM_ROUTERS:
        app.include_router(router, prefix=f"/{skellycam.__package_name__}")

    # Print all routes
    logger.debug("All registered routes:")
    for route in app.routes:
        logger.debug(f"\tRoute: {route.path} (name: {route.name})")

def customize_swagger_ui(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Welcome to the SkellyCam API 💀📸✨",
            version=skellycam.__version__,
            description=f"The FastAPI/Uvicorn/Swagger Backend UI for SkellyCam: {skellycam.__description__}",
            routes=app.routes,
        )
        # TODO - add SkellyCam logo?

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
