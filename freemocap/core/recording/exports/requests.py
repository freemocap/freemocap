"""Serializable export selections, independent of readers and application configuration."""
import hashlib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ScientificExportOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    # Compatibility override for older clients. New clients share data across formats.
    wide_csv: tuple[ChannelSelection, ...] | None = None
    data: tuple[Literal['LANDMARKS_3D', 'RAW_KEYPOINTS_3D', 'KEYPOINTS_3D', 'OVERLAY_2D', 'SEGMENT_POSES'], ...] = ('LANDMARKS_3D',)
    formats: tuple[str, ...] = ()

    @model_validator(mode='after')
    def supported(self):
        if len(set(self.formats)) != len(self.formats) or set(self.formats) - {'wide_csv', 'npy', 'npz', 'notebook'}:
            raise ValueError('Choose supported, unique export formats: wide_csv, npy, npz, notebook')
        if 'notebook' in self.formats and self.wide_csv is not None:
            raise ValueError('Notebook export uses data selections, not legacy channel overrides')
        if self.formats and self.wide_csv is None and (not self.data or len(set(self.data)) != len(self.data)):
            raise ValueError('Choose at least one data type, without duplicates')
        if self.wide_csv is not None and (not self.wide_csv or len(set(self.wide_csv)) != len(self.wide_csv)):
            raise ValueError('Choose at least one channel, without duplicates')
        return self


class ScientificExportRequest(ScientificExportOptions):
    run_id: int | None = Field(default=None, ge=0)
    expected_revision: str | None = None
    keep: bool = False


