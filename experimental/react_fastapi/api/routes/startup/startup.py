from fastapi import APIRouter

from src.config.data_paths import create_home_data_directory

startup_router = APIRouter()


@startup_router.on_event("startup")
async def handle_startup():
    create_home_data_directory()
