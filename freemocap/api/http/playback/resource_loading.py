"""Explicit failure boundaries for independently usable recording resources."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum

from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RecordingResource(StrEnum):
    RAW_VIDEO = "raw video"
    ANNOTATED_VIDEO = "annotated video"
    RECONSTRUCTION = "reconstruction"
    TIMING = "timing"
    CALIBRATION = "calibration"
    TRACKER_SCHEMA = "tracker schema"
    STATISTICS = "statistics"
    STATUS = "status"


class ResourceFailure(BaseModel):
    resource: RecordingResource
    item: str
    message: str


@contextmanager
def resource_boundary(*, resource: RecordingResource, item: str,
                      errors: list[ResourceFailure]) -> Iterator[None]:
    """Return each resource failure to the client without discarding its siblings."""
    try:
        yield
    except Exception as error:
        message = str(error.detail) if isinstance(error, HTTPException) else f"{type(error).__name__}: {error}"
        errors.append(ResourceFailure(resource=resource, item=item, message=message))
        logger.error("Unable to load %s (%s): %s", resource, item, message, exc_info=True)
