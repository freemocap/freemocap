"""Server-owned output controls; these commands never start acquisition."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.streaming.outputs.contracts import (
    OutputCapability, OutputConflictError, OutputState, OutputUnavailableError, StartOutputRequest,
)
from freemocap.core.streaming.outputs.manager import StreamingOutputManager

streaming_router = APIRouter(prefix="/streaming", tags=["Streaming outputs"])


def get_streaming_outputs() -> StreamingOutputManager:
    return get_freemocap_app().streaming_outputs


@streaming_router.get("/protocols", operation_id="streaming_list_protocols")
async def list_protocols(manager: StreamingOutputManager = Depends(get_streaming_outputs)) -> list[OutputCapability]:
    return manager.capabilities()


@streaming_router.get("/outputs", operation_id="streaming_list_outputs")
async def list_outputs(manager: StreamingOutputManager = Depends(get_streaming_outputs)) -> list[OutputState]:
    return manager.list_outputs()


@streaming_router.post("/outputs", status_code=201, operation_id="streaming_create_output",
                       responses={404: {"description": "Unknown protocol"}, 409: {"description": "Source or capacity conflict"},
                                  503: {"description": "Protocol runtime unavailable"}})
async def create_output(request: StartOutputRequest,
                        manager: StreamingOutputManager = Depends(get_streaming_outputs)) -> OutputState:
    if request.protocol not in manager.protocols:
        raise HTTPException(404, "Unknown streaming protocol")
    try:
        return await manager.start(request)
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_context=False, include_url=False)) from error
    except OutputConflictError as error:
        raise HTTPException(409, str(error)) from error
    except OutputUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@streaming_router.get("/outputs/{output_id}", operation_id="streaming_get_output",
                      responses={404: {"description": "Unknown output"}})
async def get_output(output_id: str,
                     manager: StreamingOutputManager = Depends(get_streaming_outputs)) -> OutputState:
    try:
        return manager.get(output_id)
    except KeyError as error:
        raise HTTPException(404, "Unknown streaming output") from error


@streaming_router.delete("/outputs/{output_id}", operation_id="streaming_stop_output",
                         responses={404: {"description": "Unknown output"}})
async def stop_output(output_id: str,
                      manager: StreamingOutputManager = Depends(get_streaming_outputs)) -> OutputState:
    # Narrow the lookup: emitter cleanup failures must not be reported as 404.
    try:
        manager.get(output_id)
    except KeyError as error:
        raise HTTPException(404, "Unknown streaming output") from error
    return await manager.stop(output_id)
