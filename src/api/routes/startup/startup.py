import aiomultiprocess
from fastapi import APIRouter

startup_router = APIRouter()


@startup_router.on_event("startup")
async def handle_startup():
    aiomultiprocess.set_start_method("spawn")
    # get_or_create_cams()
