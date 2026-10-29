"""Keep or overwrite a validated stage result without mixing retained runs."""

from collections.abc import Callable, Iterable, Iterator

import pyarrow as pa
import pyarrow.compute as pc
from freemocap.core.recording.data_descriptors.stage_provenance import stage_provenance

from freemocap.core.pipeline.posthoc.stage_execution_plan import (
    StageExecutionPlan,
    retained_run,
)
from freemocap.core.recording.sample_encoding.arrow_schema import SAMPLE_SCHEMA
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    RecordingMetadata,
    RunDescriptor,
    channel_key,
)
from freemocap.core.recording.parquet_storage.parquet_reader import read_batches, read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import publish_recording
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def channel_selection_mask(*, batch: pa.RecordBatch,
    channel_keys: set[tuple[str, str, str | None, str]],
) -> pa.Array:
    """Match complete channel identities without expanding scalar rows in Python."""
    # Our writer emits single-channel batches. Establish that identity once,
    # avoiding a full array comparison for every candidate channel.
    identity = []
    for name in ("sensor_group", "source", "reference_frame", "channel"):
        values = pc.unique(batch.column(name))
        if len(values) != 1:
            break
        identity.append(values[0].as_py())
    if len(identity) == 4:
        return pa.repeat(pa.scalar(tuple(identity) in channel_keys), batch.num_rows)
    selected = pa.repeat(pa.scalar(False), batch.num_rows)
    for group, source, reference, kind in channel_keys:
        matches = pc.and_(pc.equal(batch.column("sensor_group"), group),
                          pc.equal(batch.column("source"), source))
        matches = pc.and_(matches, pc.equal(batch.column("channel"), kind))
        reference_matches = pc.is_null(batch.column("reference_frame")) if reference is None else (
            pc.equal(batch.column("reference_frame"), reference))
        selected = pc.or_(selected, pc.fill_null(pc.and_(matches, reference_matches), False))
    return selected


def checkpoint_batches(
    *,
    structure: RecordingStructure,
    metadata: RecordingMetadata,
    plan: StageExecutionPlan,
    result: RunDescriptor,
    computed_batches: Iterable[pa.RecordBatch],
) -> Iterator[pa.RecordBatch]:
    retained = retained_run(base=metadata.runs[plan.base_run_id], plan=plan)
    reused_keys = {channel_key(channel=channel) for channel in retained.channels}
    computed_keys = {
        channel_key(channel=channel) for channel in result.channels
    } - reused_keys
    for run_id, run in metadata.runs.items():
        if run_id != plan.target_run_id:
            yield from read_batches(
                path=structure.data_parquet_path,
                run_id=run_id,
                sensor_groups=tuple(run.sensor_groups),
            )
    for batch in read_batches(
        path=structure.data_parquet_path,
        run_id=plan.base_run_id,
        sensor_groups=tuple(metadata.runs[plan.base_run_id].sensor_groups),
    ):
        mask = channel_selection_mask(batch=batch, channel_keys=reused_keys)
        reused = batch.filter(mask)
        if reused.num_rows:
            yield reused.set_column(
                SAMPLE_SCHEMA.get_field_index("run_id"),
                SAMPLE_SCHEMA.field("run_id"),
                pa.repeat(pa.scalar(plan.target_run_id, type=pa.int64()), reused.num_rows),
            )
    for batch in computed_batches:
        allowed = pc.and_(pc.equal(batch.column("run_id"), plan.target_run_id),
                          channel_selection_mask(batch=batch, channel_keys=computed_keys))
        if batch.num_rows and not pc.all(pc.fill_null(allowed, False)).as_py():
            raise ValueError("Computed batch writes outside the planned target channels")
        yield batch


def publish_checkpoint(
    *,
    structure: RecordingStructure,
    metadata: RecordingMetadata,
    plan: StageExecutionPlan,
    result: RunDescriptor,
    computed_batches: Iterable[pa.RecordBatch],
    cancelled: Callable[[], bool] = lambda: False,
) -> RecordingMetadata:
    """Caller holds the recording lock and verifies the input snapshot before saving."""
    if read_metadata(path=structure.data_parquet_path) != metadata:
        raise ValueError("Recording changed after stage planning")
    retained = retained_run(base=metadata.runs[plan.base_run_id], plan=plan)
    result_channels = {channel_key(channel=item): item for item in result.channels}
    channel_sources = {channel.source for channel in retained.channels} | {
        item.channel.source for item in retained.static_channels
    }
    channel_models = {retained.sources[name].definition.get('model_id')
        for name in channel_sources if name in retained.sources}
    fit_models = {retained.sources[fit.source].definition.get('model_id')
        for fit in retained.scale_fits if fit.source in retained.sources}
    for name, model in retained.models.items():
        proposed = result.models.get(name)
        if name in channel_models and proposed != model:
            raise ValueError(
                "Result must preserve scientific models used by retained outputs"
            )
        if name in fit_models and proposed is not model:
            # RecordingFitInputs excludes placement from scale evidence. A new
            # anchor is safe only when no retained channel still uses the old pose.
            if proposed is None or definition_signature(
                proposed.model_dump(exclude={"anchor_segment_name"})
            ) != definition_signature(model.model_dump(exclude={"anchor_segment_name"})):
                raise ValueError("Result must preserve scientific models used by retained scale fits")
    retained_references = {channel.reference_frame for channel in retained.channels}
    retained_references.update(item.channel.reference_frame for item in retained.static_channels)
    retained_references.update(fit.reference_frame for fit in retained.scale_fits)
    for name in retained_references - {None}:
        previous, proposed = retained.reference_frames.get(name), result.reference_frames.get(name)
        if previous is not None and 'calibration_camera_id' in previous and proposed is not None:
            # Camera assignment is metadata about pixel coordinates, not a change
            # to the camera's pixel coordinate system itself.
            previous = {key: value for key, value in previous.items() if key != 'calibration_camera_id'}
            proposed = {key: value for key, value in proposed.items() if key != 'calibration_camera_id'}
        if proposed != previous:
            raise ValueError('Cannot change coordinate definitions used by unselected saved results; existing data was not replaced')
    for fit in retained.scale_fits:
        if fit not in result.scale_fits:
            raise ValueError("Result must preserve reusable scale fits")
    for fit in result.scale_fits:
        if fit not in retained.scale_fits and (
            fit.sensor_group not in plan.sensor_groups
            or ProcessingStage.SCALE_FIT not in plan.execute
        ):
            raise ValueError("Result contains a scale fit outside the executed stages")
    for channel in retained.channels:
        if result_channels.get(channel_key(channel=channel)) != channel:
            raise ValueError("Result must preserve reusable channel definitions")
    for item in retained.static_channels:
        if item not in result.static_channels:
            raise ValueError("Result must preserve reusable static measurements")
    for checkpoint in retained.checkpoints:
        if checkpoint not in result.checkpoints:
            raise ValueError("Result must preserve reusable checkpoints")
    for group in retained.sensor_groups:
        previous = stage_provenance(retained.processing, group).stages
        current = stage_provenance(result.processing, group).stages
        if any(current.get(stage) != record for stage, record in previous.items()):
            raise ValueError("Result must preserve reusable stage provenance")
        for stage, record in current.items():
            if record != previous.get(stage) and (group not in plan.sensor_groups or stage not in plan.execute):
                raise ValueError("Result records provenance outside executed stages")
    for checkpoint in result.checkpoints:
        if checkpoint not in retained.checkpoints and (
            checkpoint.sensor_group not in plan.sensor_groups
            or checkpoint.stage not in plan.execute
        ):
            raise ValueError("Result claims completion outside the executed stages")
    if result.sensor_groups != metadata.runs[plan.base_run_id].sensor_groups:
        raise ValueError("Stage checkpoint cannot change the recording sample grids")
    for channel in result.channels:
        if channel not in retained.channels and (
            channel.sensor_group not in plan.sensor_groups
            or channel.stage not in plan.execute
        ):
            raise ValueError("Result contains a channel outside the executed stages")
    for item in result.static_channels:
        if item not in retained.static_channels and (
            item.channel.sensor_group not in plan.sensor_groups
            or item.channel.stage not in plan.execute
        ):
            raise ValueError(
                "Result contains a static channel outside the executed stages"
            )
    runs = dict(metadata.runs)
    runs[plan.target_run_id] = result
    published = RecordingMetadata(
        recording_id=metadata.recording_id,
        selected_run_id=plan.target_run_id,
        recording_info=metadata.recording_info,
        runs=runs,
    )
    publish_recording(
        structure=structure,
        metadata=published,
        cancelled=cancelled,
        batches=checkpoint_batches(
            structure=structure,
            metadata=metadata,
            plan=plan,
            result=result,
            computed_batches=computed_batches,
        ),
    )
    return published
