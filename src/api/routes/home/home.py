from fastapi import APIRouter

home_router = APIRouter()


@home_router.get("/")
async def hello():
    response_string = "hello :D"
    print(f"response string: {response_string}")
    return response_string
