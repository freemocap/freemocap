import logging
import time
import traceback

from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)


def add_middleware(app: FastAPI) -> None:
    logger.debug("Adding middleware...")

    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        logger.api(f"Received request: {request.method} {request.url}")
        start_time = time.time()

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time

            # For error responses, consume the body to log it
            if response.status_code >= 400:
                # Consume the entire response body
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk

                # Try to decode and log the error
                try:
                    error_content = response_body.decode("utf-8")
                    logger.error(
                        f"Request FAILED: {request.method} {request.url} "
                        f"[{response.status_code}] in {process_time:.6f}s - "
                        f"Error: {error_content}"
                    )
                except UnicodeDecodeError:
                    logger.error(
                        f"Request FAILED: {request.method} {request.url} "
                        f"[{response.status_code}] in {process_time:.6f}s - "
                        f"Error body could not be decoded (length: {len(response_body)} bytes)"
                    )

                # Recreate the response with the consumed body so the client still gets it
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            else:
                logger.api(
                    f"Handled Request: {request.url} processed in {process_time:.6f} seconds "
                    f"and returned status code: {response.status_code}"
                )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request EXCEPTION: {request.method} {request.url} "
                f"failed in {process_time:.6f}s with exception: {type(e).__name__}: {str(e)}"
            )
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise