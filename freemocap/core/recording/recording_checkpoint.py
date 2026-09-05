"""Keep or overwrite a validated stage result without mixing retained runs."""

from collections.abc import Iterable, Iterator

import pyarrow as pa

from freemocap.core.pipeline.posthoc.stage_execution_plan import (
    StageExecutionPlan,
    retained_run,
)
from freemocap.core.recording.recording_data import SAMPLE_SCHEMA
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.recording.recording_metadata import (
    RecordingMetadata,
    RunDescriptor,
    channel_key,
)
from freemocap.core.recording.recording_reader import read_batches, read_metadata
from freemocap.core.recording.recording_writer import publish_recording
from freemocap.system.recording_structure.recording_structure import RecordingStructure


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
        columns = batch.to_pydict()
        mask = pa.array(
            [
                (group, source, reference, kind) in reused_keys
                for group, source, reference, kind in zip(
                    columns["sensor_group"],
                    columns["source"],
                    columns["reference_frame"],
                    columns["channel"],
                    strict=True,
                )
            ]
        )
        reused = batch.filter(mask)
        if reused.num_rows:
            yield reused.set_column(
                SAMPLE_SCHEMA.get_field_index("run_id"),
                SAMPLE_SCHEMA.field("run_id"),
                pa.array([plan.target_run_id] * reused.num_rows, type=pa.int64()),
            )
    for batch in computed_batches:
        columns = batch.to_pydict()
        for run_id, group, source, reference, kind in zip(
            columns["run_id"],
            columns["sensor_group"],
            columns["source"],
            columns["reference_frame"],
            columns["channel"],
            strict=True,
        ):
            if (
                run_id != plan.target_run_id
                or (group, source, reference, kind) not in computed_keys
            ):
                raise ValueError(
                    "Computed batch writes outside the planned target channels"
                )
        yield batch


def publish_checkpoint(
    *,
    structure: RecordingStructure,
    metadata: RecordingMetadata,
    plan: StageExecutionPlan,
    result: RunDescriptor,
    computed_batches: Iterable[pa.RecordBatch],
) -> RecordingMetadata:
    """Caller holds the recording lock, including planning and numerical work."""
    if read_metadata(path=structure.data_parquet_path) != metadata:
        raise ValueError("Recording changed after stage planning")
    retained = retained_run(base=metadata.runs[plan.base_run_id], plan=plan)
    result_channels = {channel_key(channel=item): item for item in result.channels}
    retained_model_sources = {channel.source for channel in retained.channels} | {
        fit.source for fit in retained.scale_fits
    }
    for name, model in retained.models.items():
        if name in retained_model_sources and result.models.get(name) != model:
            raise ValueError(
                "Result must preserve scientific models used by retained outputs"
            )
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
        batches=checkpoint_batches(
            structure=structure,
            metadata=metadata,
            plan=plan,
            result=result,
            computed_batches=computed_batches,
        ),
    )
    return published
