"""Diagnostic channels share recording identity, invalidation, and publication contracts."""

from dataclasses import replace
import hashlib
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
import yaml
import freemocap.core.recording.parquet_storage.parquet_writer as recording_writer

from freemocap.core.diagnostics.health_report import (
    AssessmentCriterion,
    MeasurementAccumulator,
    assess_measurement,
)
from freemocap.core.diagnostics.recording_health_report import (
    RecordingHealthReport,
    build_recording_health_report,
)
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import (
    StageExecutionPlan,
    retained_run,
)
from freemocap.core.recording.parquet_storage.checkpoint_publication import (
    publish_checkpoint,
)
from freemocap.core.recording.parquet_storage.parquet_writer import recording_write_lock
from freemocap.core.recording.result_processing.observation_inputs import (
    ObservationRecordingRequest,
)
from freemocap.core.recording.result_processing.observation_publication import (
    publish_posthoc_observations,
)
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import (
    NamedReprojectionDiagnostics,
    ReprojectionDiagnostics,
)
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure

pytest_plugins = ("freemocap.tests.test_reconstruction_checkpoints",)


def with_reprojection(
    *, request: ObservationRecordingRequest
) -> ObservationRecordingRequest:
    errors = np.array([[[2.0, np.nan], [4.0, 8.0]]])
    return replace(
        request,
        reprojection=NamedReprojectionDiagnostics(
            source_ids=("camera",),
            point_names=("body.wrist", "body.elbow"),
            values=ReprojectionDiagnostics(
                errors=errors,
                observed=np.isfinite(errors),
                reconstructed=np.ones_like(errors, dtype=np.bool_),
                weights=np.array([[[1.0, 0.0], [1.0, 0.0]]]),
                units="pixels",
            ),
        ),
    )


def test_canonical_channels_and_yaml_roundtrip(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    request = with_reprojection(request=publication)
    metadata = publish_posthoc_observations(request)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    table = pq.read_table(
        structure.data_parquet_path, filters=[("channel", "=", "REPROJECTION_ERROR")]
    )
    assert table["value"].to_pylist() == [2.0, None, 4.0, 8.0]
    assert table["name"].to_pylist() == ["body.wrist", "body.elbow"] * 2
    assert set(table["source"].to_pylist()) == {"camera:camera"}
    assert set(table["run_id"].to_pylist()) == {0}
    assert set(table["units"].to_pylist()) == {"px"}
    report = RecordingHealthReport.model_validate(
        yaml.safe_load((structure.output_dir / "diagnostics.yaml").read_text())
    )
    assert report == build_recording_health_report(
        path=structure.data_parquet_path, criteria=()
    )
    assert (
        report.parquet_sha256
        == hashlib.sha256(structure.data_parquet_path.read_bytes()).hexdigest()
    )
    elbow = next(
        item
        for item in report.measurements
        if item.channel == ChannelKind.REPROJECTION_ERROR and item.name == "body.elbow"
    )
    assert (
        elbow.statistics.sample_count == 1 and elbow.statistics.unavailable_count == 1
    )
    assert elbow.statistics.mean == 8.0 and elbow.assessment.status == "not_assessed"
    assert (elbow.first_frame, elbow.last_frame) == (0, 1)
    residuals = [
        item
        for item in report.measurements
        if item.channel == ChannelKind.RIGID_BODY_RESIDUALS
        and item.component == "residual"
    ]
    assert residuals and any(item.statistics.sample_count for item in residuals)
    assert all(item.statistics.unavailable_count >= 1 for item in residuals)
    assert report.runs[0].scale_fits == metadata.runs[0].scale_fits
    assert len(list(structure.full_path.glob("*.parquet"))) == 1
    assert not list(structure.output_dir.glob("*.parquet"))


def test_stage_invalidation_preserves_other_run_diagnostics(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    metadata = publish_posthoc_observations(with_reprojection(request=publication))
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    for target, invalidate in (
        (1, (ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS)),
        (
            2,
            (
                ProcessingStage.TRIANGULATION,
                ProcessingStage.FILTERING,
                ProcessingStage.SCALE_FIT,
                ProcessingStage.RECONSTRUCTION,
                ProcessingStage.BIOMECHANICS,
            ),
        ),
    ):
        plan = StageExecutionPlan(
            base_run_id=0,
            target_run_id=target,
            sensor_groups=("mocap",),
            execute=(),
            invalidate=invalidate,
        )
        with recording_write_lock(structure=structure):
            metadata = publish_checkpoint(
                structure=structure,
                metadata=metadata,
                plan=plan,
                result=retained_run(base=metadata.runs[0], plan=plan),
                computed_batches=(),
            )
    report = build_recording_health_report(
        path=structure.data_parquet_path, criteria=()
    )
    by_run = {
        run: {item.channel for item in report.measurements if item.run_id == run}
        for run in range(3)
    }
    assert ChannelKind.RIGID_BODY_RESIDUALS in by_run[0]
    assert ChannelKind.RIGID_BODY_RESIDUALS not in by_run[1]
    assert ChannelKind.REPROJECTION_ERROR in by_run[1]
    assert not by_run[2]
    assert report.selected_run_id == 2


def test_report_reassesses_saved_values_without_reconstruction(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(with_reprojection(request=publication))
    path = RecordingStructure(
        base_directory=tmp_path, recording_name="recording"
    ).data_parquet_path
    before = path.read_bytes()
    criterion = AssessmentCriterion(
        channel=ChannelKind.REPROJECTION_ERROR,
        component="error",
        units="px",
        maximum_rms=3.0,
        minimum_available_fraction=1.0,
    )
    report = build_recording_health_report(path=path, criteria=(criterion,))
    errors = {
        item.name: item
        for item in report.measurements
        if item.channel == ChannelKind.REPROJECTION_ERROR
    }
    assert errors["body.wrist"].assessment.status == "fail"
    assert errors["body.elbow"].assessment.status == "insufficient_data"
    assert errors["body.wrist"].statistics.rms == pytest.approx(np.sqrt(10.0))
    assert path.read_bytes() == before


def test_wrong_residual_reference_fails_before_replacing_output(
    publication: ObservationRecordingRequest, tmp_path: Path
) -> None:
    publish_posthoc_observations(publication)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    original_data = structure.data_parquet_path.read_bytes()
    original_report = (structure.output_dir / "diagnostics.yaml").read_bytes()
    reconstruction = publication.reconstructions[0]
    frame = reconstruction.result.frames[0]
    assert frame is not None
    readings = dict(frame.rigid_body_residuals)
    name = next(iter(readings))
    readings[name] = replace(readings[name], reference_kind="prior_live_fit")
    altered = replace(
        reconstruction,
        result=replace(
            reconstruction.result,
            frames=(
                replace(frame, rigid_body_residuals=readings),
                *reconstruction.result.frames[1:],
            ),
        ),
    )
    with pytest.raises(ValueError, match="reference must match"):
        publish_posthoc_observations(replace(publication, reconstructions=(altered,)))
    assert structure.data_parquet_path.read_bytes() == original_data
    assert (structure.output_dir / "diagnostics.yaml").read_bytes() == original_report


def test_empty_measurements_never_pass_and_invalid_numbers_raise() -> None:
    accumulator = MeasurementAccumulator()
    accumulator.add(value=None)
    assert (
        assess_measurement(statistics=accumulator.summary(), criterion=None).status
        == "insufficient_data"
    )
    with pytest.raises(ValueError, match="finite"):
        accumulator.add(value=float("inf"))
    accumulator.add(value=0.0)
    criterion = AssessmentCriterion(
        channel=ChannelKind.RIGID_BODY_RESIDUALS,
        component="residual",
        units="mm",
        maximum_rms=0.0,
        minimum_available_fraction=0.5,
    )
    assert (
        assess_measurement(statistics=accumulator.summary(), criterion=criterion).status
        == "pass"
    )


def test_report_write_failure_is_loud_and_removes_stale_report(
    publication: ObservationRecordingRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish_posthoc_observations(publication)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    assert structure.diagnostics_report_path.exists()

    def fail_report(
        *, structure: RecordingStructure, criteria: tuple[AssessmentCriterion, ...]
    ) -> None:
        raise OSError("Report destination unavailable")

    monkeypatch.setattr(recording_writer, "write_recording_health_report", fail_report)
    with pytest.raises(OSError, match="destination unavailable"):
        publish_posthoc_observations(with_reprojection(request=publication))
    assert not structure.diagnostics_report_path.exists()
    assert (
        pq.read_table(
            structure.data_parquet_path,
            filters=[("channel", "=", "REPROJECTION_ERROR")],
        ).num_rows
        == 4
    )
    assert not list(structure.full_path.glob("*.tmp"))
