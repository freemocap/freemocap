"""Validated saved 3D inputs; no video access, tracking or realignment."""
from dataclasses import dataclass, replace
from pathlib import Path

from freemocap.core.pipeline.posthoc.saved_stage_processing import select_group
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterReport
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.result_processing.saved_reconstruction import SavedPointSeries, read_saved_channel
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@dataclass(frozen=True)
class SavedSpatialSource:
    structure: RecordingStructure
    metadata: RecordingMetadata
    revision: str
    run_id: int
    group: str
    points: SavedPointSeries
    reference: SpatialReference
    numerical: RecordingReconstructionInput
    filtering: PosthocFilterReport | None


def load_saved_spatial_source(*, path: Path, config: PosthocMocapPipelineConfig) -> SavedSpatialSource:
    if config.start_stage not in ('filtering', 'scale_fit', 'reconstruction'):
        raise ValueError('Saved 3D inputs require a numerical start stage')
    structure = RecordingStructure(base_directory=path.parent, recording_name=path.name)
    with recording_write_lock(structure=structure):
        with recording_view(structure.data_parquet_path) as view:
            metadata, revision = view.metadata, view.revision
        base = metadata.runs[config.base_run_id]
        group = select_group(base, config.sensor_group)
        kind = ChannelKind.RAW_KEYPOINTS_3D if config.start_stage == 'filtering' else ChannelKind.KEYPOINTS_3D
        channels = [c for c in base.channels if c.sensor_group == group and c.kind == kind]
        if len(channels) != 1:
            raise ValueError(f'Restart requires one complete saved {kind} channel')
        points = read_saved_channel(structure=structure, metadata=metadata, run_id=config.base_run_id, channel=channels[0])
        reference = SpatialReference.model_validate(base.reference_frames[points.channel.reference_frame])
        if dict(points.channel.components) != dict.fromkeys(('x', 'y', 'z'), reference.units):
            raise ValueError('Saved 3D points must use xyz components in their declared spatial units')
        bundles = tuple(model.to_bundle() for model in base.models.values()
            if model_source_name(model.model_id) not in base.sources
            or base.sources[model_source_name(model.model_id)].definition.get('tracker') == points.channel.source)
        bundles = tuple(replace(b, anchor_segment_name=config.anchor_segment_name)
                        if b.model_id == 'standard_human' else b for b in bundles)
        if not bundles:
            raise ValueError('Saved scientific models are missing')
        saved_report = base.processing.get(group, {}).get('filtering')
        report = PosthocFilterReport.model_validate(saved_report) if saved_report is not None and kind == ChannelKind.KEYPOINTS_3D else None
        if kind == ChannelKind.KEYPOINTS_3D and report is None:
            raise ValueError('Filtered points require their saved filtering report')
        support = report.gap_filling.measured_support(points.values) if report is not None and report.gap_filling is not None else None
        numerical = RecordingReconstructionInput(bundles=bundles, keypoint_names=points.channel.names,
            keypoints_3d=points.values, measured_support=support, compute_center_of_mass=True, timing=PosthocTimingReport())
        return SavedSpatialSource(structure, metadata, revision, config.base_run_id, group, points, reference, numerical, report)


def load_saved_model_fits(source: SavedSpatialSource, numerical: RecordingReconstructionInput) -> dict:
    base = source.metadata.runs[source.run_id]
    result = {}
    for bundle in numerical.bundles:
        matches = [f for f in base.scale_fits if f.sensor_group == source.group and f.source == model_source_name(bundle.model_id)]
        if len(matches) != 1:
            raise ValueError(f'Missing unique saved scale fit for {bundle.model_id}; restart at scale fitting')
        fit = matches[0]
        if (fit.reference_frame != source.reference.name or fit.units != source.reference.units
                or fit.inputs != numerical.fit_inputs(bundle)):
            raise ValueError('Saved scale fit inputs changed; restart at scale fitting')
        result[bundle.model_id] = fit.for_reconstruction()
    return result
