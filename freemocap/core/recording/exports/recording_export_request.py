"""Kind-specific saved-recording export requests; identity comes from the route."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.blender.blender_export_config import BlenderExportConfig
from freemocap.core.recording.exports.requests import ExportRequest
from freemocap.core.recording.exports.tall_csv import TallCsvRequest


class ChannelExportRequest(ExportRequest):
    kind: Literal['channels'] = 'channels'
    formats: tuple[Literal['wide_csv', 'npy', 'npz', 'notebook'], ...] = Field(min_length=1)


class TallCsvExportRequest(TallCsvRequest):
    kind: Literal['tall_csv'] = 'tall_csv'


class BlenderRecordingExportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra='forbid', frozen=True)
    kind: Literal['blender'] = 'blender'
    blender_exe_path: str | None = Field(default=None, alias='blenderExePath')
    auto_open_blend_file: bool = Field(default=True, alias='autoOpenBlendFile')
    route: Literal['auto', 'legacy_npy', 'parquet_segments', 'parquet_constraints'] = 'auto'
    package: str | None = None
    trajectory_channel: Literal['LANDMARKS_3D', 'MAPPED_KEYPOINTS_3D'] = Field(default='LANDMARKS_3D', alias='trajectoryChannel')
    run_id: int | None = Field(default=None, alias='runId', ge=0)
    expected_revision: str | None = None
    sensor_group: str | None = Field(default=None, alias='sensorGroup')
    development_build_hash: str | None = Field(default=None, alias='developmentBuildHash', pattern=r'^[0-9a-f]{64}$')
    blender_export_config: BlenderExportConfig = Field(default_factory=BlenderExportConfig, alias='blenderExportConfig')


RecordingExportRequest = Annotated[ChannelExportRequest | TallCsvExportRequest | BlenderRecordingExportRequest,
                                  Field(discriminator='kind')]
