"""Resume numerical processing from validated canonical recording channels."""

from pathlib import Path


from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.recording_descriptor import RunDescriptor
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


RESUME_STAGES = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')


def recording_structure(path: str) -> RecordingStructure:
    folder = Path(path).expanduser()
    return RecordingStructure(base_directory=folder.parent, recording_name=folder.name)


def select_group(run: RunDescriptor, requested: str | None) -> str:
    groups = {c.sensor_group for c in run.channels if c.kind in
              (ChannelKind.OVERLAY_2D, ChannelKind.RAW_KEYPOINTS_3D, ChannelKind.KEYPOINTS_3D)}
    if requested is not None:
        if requested not in groups:
            raise ValueError('The selected sensor group has no saved mocap inputs')
        return requested
    if len(groups) != 1:
        raise ValueError('Select a sensor group for reprocessing')
    return next(iter(groups))


def inspect_saved_stages(path: str) -> dict:
    """Descriptor inventory; readers validate full component grids before reuse."""
    structure = recording_structure(path)
    if not structure.data_parquet_path.exists():
        return dict(runs=[], selected_run_id=0)
    metadata = read_metadata(path=structure.data_parquet_path)
    runs = []
    for run_id, run in metadata.runs.items():
        groups = []
        for group in run.sensor_groups:
            kinds = {c.kind for c in run.channels if c.sensor_group == group}
            if not kinds.intersection((ChannelKind.OVERLAY_2D, ChannelKind.RAW_KEYPOINTS_3D, ChannelKind.KEYPOINTS_3D)):
                continue
            completed = {c.stage for c in run.checkpoints if c.sensor_group == group}
            stages = dict(
                observations=ChannelKind.OVERLAY_2D in kinds and ChannelKind.TIMESTAMPS in kinds,
                triangulation=ChannelKind.RAW_KEYPOINTS_3D in kinds,
                filtering=ChannelKind.KEYPOINTS_3D in kinds,
                scale_fit=any(f.sensor_group == group for f in run.scale_fits),
                reconstruction=ProcessingStage.RECONSTRUCTION in completed and {ChannelKind.LANDMARKS_3D, ChannelKind.MAPPED_KEYPOINTS_3D}.issubset(kinds),
            )
            groups.append(dict(sensor_group=group, stages=stages))
        runs.append(dict(run_id=run_id, groups=groups))
    return dict(runs=runs, selected_run_id=metadata.selected_run_id)
