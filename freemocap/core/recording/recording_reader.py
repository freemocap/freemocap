"""Read the exact recording file and its embedded scientific description."""

from collections.abc import Iterator
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from freemocap.core.recording.recording_data import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from freemocap.core.recording.recording_metadata import RecordingMetadata, StaticChannel
from freemocap.core.recording.recording_metadata import RunDescriptor
from freemocap.core.recording.scale_fit_channels import scale_fit_channels


def read_static_channels(run: RunDescriptor) -> tuple[StaticChannel, ...]:
    """Return authored static channels and views of the recorded global fit."""
    return (*run.static_channels, *scale_fit_channels(run))


def read_metadata(*, path: Path) -> RecordingMetadata:
    with pq.ParquetFile(path) as parquet:
        schema = parquet.schema_arrow
        if not schema.equals(SAMPLE_SCHEMA, check_metadata=False):
            raise ValueError(f"Invalid recording schema: {path}")
        payload = (schema.metadata or {}).get(DESCRIPTOR_KEY)
        if payload is None:
            raise ValueError(f"Missing recording descriptor: {path}")
        return RecordingMetadata.model_validate_json(payload)


def read_batches(
    *, path: Path, run_id: int, sensor_groups: tuple[str, ...]
) -> Iterator[pa.RecordBatch]:
    metadata = read_metadata(path=path)
    run = metadata.runs[run_id]
    if not sensor_groups or not set(sensor_groups).issubset(run.sensor_groups):
        raise ValueError("Read requires known sensor groups")
    with pq.ParquetFile(path) as parquet:
        for batch in parquet.iter_batches(batch_size=65536):
            selected = pc.and_(
                pc.equal(batch.column("run_id"), run_id),
                pc.is_in(
                    batch.column("sensor_group"), value_set=pa.array(sensor_groups)
                ),
            )
            result = batch.filter(selected).replace_schema_metadata(None)
            if result.num_rows:
                yield result


def static_samples(
    *, channel: StaticChannel, run_id: int, frame_number: int, timestamp_s: float
) -> pa.RecordBatch:
    """Expand a frozen measurement at a caller-selected group sample time."""
    definition = channel.channel
    rows: list[dict[str, object]] = []
    for name, components in channel.values.items():
        for component, value in components.items():
            rows.append(
                dict(
                    timestamp_s=timestamp_s,
                    sensor_group=definition.sensor_group,
                    frame_number=frame_number,
                    source=definition.source,
                    reference_frame=definition.reference_frame,
                    channel=definition.kind,
                    name=name,
                    component=component,
                    value=value,
                    units=definition.components[component],
                    run_id=run_id,
                )
            )
    return pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
