import logging
import os

from fastapi import APIRouter
from starlette.responses import HTMLResponse

logger = logging.getLogger(__name__)

data_visualization_router = APIRouter()


@data_visualization_router.get("/", response_class=HTMLResponse)
def serve_data_vizualization():
    logger.info("Serving UI HTML to `/data_visualization`")
    file_path = os.path.join(os.path.dirname(__file__), 'd3_datavis.html')
    with open(file_path, 'r') as file:
        ui_html_string = file.read()
    return HTMLResponse(content=ui_html_string, status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(data_visualization_router, host="localhost", port=8000)
