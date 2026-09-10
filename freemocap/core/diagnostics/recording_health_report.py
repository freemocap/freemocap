"""Regenerate a run-scoped YAML report from canonical Parquet diagnostic channels."""

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Literal

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

from freemocap.core.diagnostics.health_report import (
    AssessmentCriterion,
    DiagnosticModel,
    MeasurementAccumulator,
    MeasurementAssessment,
    MeasurementStatistics,
    assess_measurement,
)
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.parquet_storage.parquet_reader import metadata_from_schema
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


DIAGNOSTIC_CHANNELS = (
    ChannelKind.REPROJECTION_ERROR,
    ChannelKind.RECONSTRUCTION_COVERAGE,
    ChannelKind.TRIANGULATION_WEIGHTS,
    ChannelKind.RIGID_BODY_RESIDUALS,
)


class MeasurementReport(DiagnosticModel):
    run_id: int
    sensor_group: str
    source: str
    reference_frame: str | None
    channel: ChannelKind
    name: str
    component: str
    units: str
    first_frame: int | None
    last_frame: int | None
    start_time_s: float | None
    end_time_s: float | None
    statistics: MeasurementStatistics
    assessment: MeasurementAssessment


class RunReport(DiagnosticModel):
    run_id: int
    descriptor_sha256: str
    sensor_groups: tuple[str, ...]
    sources: tuple[str, ...]
    models: tuple[str, ...]
    scale_fits: tuple[RecordingScaleFit, ...]
    diagnostic_channels: tuple[ChannelKind, ...]


class RecordingHealthReport(DiagnosticModel):
    schema_version: Literal[1] = 1
    recording_id: str
    parquet_file: str
    parquet_sha256: str
    selected_run_id: int
    criteria: tuple[AssessmentCriterion, ...]
    runs: tuple[RunReport, ...]
    measurements: tuple[MeasurementReport, ...]


@dataclass(slots=True)
class TrajectoryStatistics:
    measurements: MeasurementAccumulator = field(default_factory=MeasurementAccumulator)
    first_frame: int | None = None
    last_frame: int | None = None
    start_time_s: float | None = None
    end_time_s: float | None = None


def build_recording_health_report(
    *, path: Path, criteria: tuple[AssessmentCriterion, ...]
) -> RecordingHealthReport:
    criterion_index = {
        (item.channel, item.component, item.units): item for item in criteria
    }
    if len(criterion_index) != len(criteria):
        raise ValueError("Diagnostic assessment criteria must be unique")
    trajectories: dict[
        tuple[int, str, str, str | None, ChannelKind, str, str, str],
        TrajectoryStatistics,
    ] = {}
    with path.open("rb") as source:
        fingerprint = hashlib.file_digest(source, "sha256").hexdigest()
        source.seek(0)
        with pq.ParquetFile(source) as parquet:
            metadata = metadata_from_schema(schema=parquet.schema_arrow, path=path)
            for run_id, run in metadata.runs.items():
                for channel in run.channels:
                    if channel.kind in DIAGNOSTIC_CHANNELS:
                        for name in channel.names:
                            for component, units in channel.components.items():
                                key = (
                                    run_id,
                                    channel.sensor_group,
                                    channel.source,
                                    channel.reference_frame,
                                    channel.kind,
                                    name,
                                    component,
                                    units,
                                )
                                trajectories[key] = TrajectoryStatistics()
            for batch in parquet.iter_batches(batch_size=65536):
                selected = batch.filter(
                    pc.is_in(
                        batch.column("channel"), value_set=pa.array(DIAGNOSTIC_CHANNELS)
                    )
                )
                for row in selected.to_pylist():
                    key = (
                        row["run_id"],
                        row["sensor_group"],
                        row["source"],
                        row["reference_frame"],
                        ChannelKind(row["channel"]),
                        row["name"],
                        row["component"],
                        row["units"],
                    )
                    trajectory = trajectories[key]
                    trajectory.measurements.add(value=row["value"])
                    if trajectory.first_frame is None:
                        trajectory.first_frame = row["frame_number"]
                        trajectory.start_time_s = row["timestamp_s"]
                    trajectory.last_frame = row["frame_number"]
                    trajectory.end_time_s = row["timestamp_s"]
    measurements: list[MeasurementReport] = []
    for (
        run_id,
        group,
        source_id,
        reference,
        channel,
        name,
        component,
        units,
    ), trajectory in trajectories.items():
        statistics = trajectory.measurements.summary()
        if (
            statistics.sample_count + statistics.unavailable_count
            != metadata.runs[run_id].sensor_groups[group].sample_count
        ):
            raise ValueError(
                "Diagnostic report requires complete declared trajectory coverage"
            )
        measurements.append(
            MeasurementReport(
                run_id=run_id,
                sensor_group=group,
                source=source_id,
                reference_frame=reference,
                channel=channel,
                name=name,
                component=component,
                units=units,
                first_frame=trajectory.first_frame,
                last_frame=trajectory.last_frame,
                start_time_s=trajectory.start_time_s,
                end_time_s=trajectory.end_time_s,
                statistics=statistics,
                assessment=assess_measurement(
                    statistics=statistics,
                    criterion=criterion_index.get((channel, component, units)),
                ),
            )
        )
    return RecordingHealthReport(
        recording_id=metadata.recording_id,
        parquet_file=path.name,
        parquet_sha256=fingerprint,
        selected_run_id=metadata.selected_run_id,
        criteria=criteria,
        runs=tuple(
            RunReport(
                run_id=run_id,
                descriptor_sha256=hashlib.sha256(
                    run.model_dump_json().encode()
                ).hexdigest(),
                sensor_groups=tuple(run.sensor_groups),
                sources=tuple(run.sources),
                models=tuple(run.models),
                scale_fits=run.scale_fits,
                diagnostic_channels=tuple(
                    dict.fromkeys(
                        channel.kind
                        for channel in run.channels
                        if channel.kind in DIAGNOSTIC_CHANNELS
                    )
                ),
            )
            for run_id, run in metadata.runs.items()
        ),
        measurements=tuple(measurements),
    )


def write_recording_health_report(
    *, structure: RecordingStructure, criteria: tuple[AssessmentCriterion, ...]
) -> None:
    """Caller holds the recording lock so the report describes a stable publication."""
    report = build_recording_health_report(
        path=structure.data_parquet_path, criteria=criteria
    )
    structure.output_dir.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=structure.output_dir, suffix=".yaml.tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            yaml.safe_dump(report.model_dump(mode="json"), output, sort_keys=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(structure.diagnostics_report_path)
    finally:
        temporary.unlink(missing_ok=True)
