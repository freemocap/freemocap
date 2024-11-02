import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI):
    logger.debug("Adding middleware...")

    # @app.middleware("http")
    # async def log_requests(request: Request, call_next):
    #     start_time = time.time()
    #     response: Response = await call_next(request)
    #     process_time = time.time() - start_time
    #     logger.debug(
    #         f"Request: {request.url} processed in {process_time:.6f} seconds and returned status code: {response.status_code}")
    #     get_app_state().log_api_call(url_path=request.url.path,
    #                                  start_time=start_time,
    #                                  process_time=process_time,
    #                                  status_code=response.status_code)
    #     return response
