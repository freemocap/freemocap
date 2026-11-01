"""Saved recording descriptors for clients that do not need rendering projections."""
from pydantic import BaseModel

from freemocap.core.recording.data_descriptors.recording_descriptor import Channel, StaticChannel
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.parquet_storage.parquet_reader import read_static_channels
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class RunSummary(BaseModel):
    run_id: int
    sensor_groups: tuple[str, ...]
    channel_count: int


class RunInventory(BaseModel):
    revision: str | None
    selected_run_id: int | None
    runs: tuple[RunSummary, ...]


class RunChannels(BaseModel):
    run_id: int
    revision: str
    channels: tuple[Channel, ...]
    static_channels: tuple[StaticChannel, ...]


def recording_runs(structure: RecordingStructure) -> RunInventory:
    if not structure.data_parquet_path.is_file():
        return RunInventory(revision=None, selected_run_id=None, runs=())
    with recording_view(structure.data_parquet_path) as view:
        return RunInventory(revision=view.revision, selected_run_id=view.metadata.selected_run_id,
                            runs=tuple(RunSummary(run_id=key, sensor_groups=tuple(run.sensor_groups),
                                                  channel_count=len(run.channels))
                                       for key, run in view.metadata.runs.items()))


def recording_channels(structure: RecordingStructure, run_id: int) -> RunChannels:
    with recording_view(structure.data_parquet_path) as view:
        if run_id not in view.metadata.runs:
            raise KeyError(f'Unknown recording run: {run_id}')
        run = view.metadata.runs[run_id]
        return RunChannels(run_id=run_id, revision=view.revision, channels=run.channels,
                           static_channels=read_static_channels(run))
