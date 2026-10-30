"""Immutable channel identity shared by storage consumers and export requests."""
import hashlib
from pydantic import BaseModel, ConfigDict


class ChannelSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    sensor_group: str
    source: str
    reference_frame: str | None
    channel: str
    static: bool = False

    @property
    def key(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:24]
