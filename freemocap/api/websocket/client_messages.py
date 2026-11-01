"""Validate client display hints before they reach camera image scaling."""
from pydantic import BaseModel, Field, FiniteFloat


class ClientMessageError(ValueError):
    """Invalid input closes its connection, without changing application state."""


class DisplayImageSize(BaseModel):
    width: FiniteFloat
    height: FiniteFloat


class FrameAcknowledgment(BaseModel):
    frameNumber: int = Field(ge=0)
    displayImageSizes: dict[str, DisplayImageSize] | None = None

    def display_sizes(self) -> dict[str, dict[str, float]] | None:
        return {camera: size.model_dump() for camera, size in (self.displayImageSizes or {}).items()
                if size.width > 0 and size.height > 0} or None
