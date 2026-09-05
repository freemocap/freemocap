"""Recording contracts across rates, failures and retained processing results."""

from pathlib import Path
from dataclasses import replace
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit
from freemocap.core.recording.recording_scale_fit import RecordingScaleFit
from freemocap.core.recording.sample_conventions import SampleUnit
from freemocap.core.pipeline.posthoc.execution_inputs import CameraExecutionInputs
from filelock import Timeout

import pyarrow as pa
import pytest

from freemocap.core.pipeline.posthoc.processing_request import (
    ProcessingRequest,
    ProcessingStage,
    STAGE_ORDER,
)
from freemocap.core.pipeline.posthoc.stage_execution_plan import (
    build_execution_plan,
    retained_run,
)
from freemocap.core.recording.recording_data import SAMPLE_SCHEMA
from freemocap.core.recording.recording_checkpoint import publish_checkpoint
from freemocap.core.recording.recording_metadata import (
    Channel,
    RecordingMetadata,
    RunDescriptor,
    SensorGroup,
    Source,
    StageCheckpoint,
    StaticChannel,
)
from freemocap.core.recording.recording_reader import (
    read_batches,
    read_metadata,
    static_samples,
)
from freemocap.core.recording.recording_writer import (
    publish_recording,
    recording_write_lock,
    repair_metadata_mirror,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def test_body_detection_restart_preserves_camera_geometry() -> None:
    plan = build_execution_plan(
        inputs={"mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())},
        request=ProcessingRequest(
            sensor_groups=("mocap",),
            start_stage=ProcessingStage.OBSERVATIONS,
        ),
        metadata=metadata_fixture(),
        signatures={"mocap": {stage: stage.value for stage in STAGE_ORDER}},
    )
    assert plan.execute[0] == ProcessingStage.OBSERVATIONS

    assert ProcessingStage.TIMING not in plan.invalidate
    assert ProcessingStage.RECONSTRUCTION in plan.execute


def test_scale_fit_keep_and_overwrite_preserve_other_results(tmp_path: Path) -> None:
    metadata = metadata_fixture()
    fit = RecordingScaleFit(
        sensor_group="mocap",
        source="human",
        reference_frame="world",
        units=SampleUnit.MILLIMETERS,
        fit=ModelScaleFit(
            fitted_scale=100.0,
            segment_scales={"segment": 100.0},
            segment_lengths={"segment": 10.0},
            measured_segment_names=frozenset({"segment"}),
            voting_segment_names=frozenset({"segment"}),
        ),
    )
    run = metadata.runs[0].model_copy(
        update={
            "reference_frames": {"world": {"units": SampleUnit.MILLIMETERS}},
            "scale_fits": (fit, fit.model_copy(update={"sensor_group": "eye"})),
        }
    )
    metadata = RecordingMetadata(
        recording_id="recording", selected_run_id=0, runs={0: run}
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
        for keep, size in ((True, 102.0), (False, 103.0)):
            plan = build_execution_plan(
                request=ProcessingRequest(
                    sensor_groups=("mocap",),
                    keep=keep,
                    start_stage=ProcessingStage.SCALE_FIT,
                    stop_stage=ProcessingStage.SCALE_FIT,
                ),
                inputs={"mocap": CameraExecutionInputs(camera_ids=(), geometry=())},
                metadata=metadata,
                signatures={
                    "mocap": {
                        ProcessingStage.FILTERING: ProcessingStage.FILTERING.value
                    }
                },
            )
            retained = retained_run(base=metadata.runs[0], plan=plan)
            assert (
                len(retained.scale_fits) == 1
                and retained.scale_fits[0].sensor_group == "eye"
            )
            replacement = fit.model_copy(
                update={
                    "fit": replace(
                        fit.fit, fitted_scale=size, segment_scales={"segment": size}
                    )
                }
            )
            result = retained.model_copy(
                update={"scale_fits": (*retained.scale_fits, replacement)}
            )
            metadata = publish_checkpoint(
                structure=structure,
                metadata=metadata,
                plan=plan,
                result=result,
                computed_batches=(),
            )
        assert metadata.runs[0].scale_fits[-1].fit.fitted_scale == 103.0
        assert metadata.runs[1].scale_fits[-1].fit.fitted_scale == 102.0
        assert read_metadata(path=structure.data_parquet_path) == metadata


def test_reconstruction_restart_preserves_scale_fit() -> None:
    fit = RecordingScaleFit(
        sensor_group="mocap",
        source="human",
        reference_frame="world",
        units=SampleUnit.MILLIMETERS,
        fit=None,
    )
    base = (
        metadata_fixture()
        .runs[0]
        .model_copy(
            update={
                "reference_frames": {"world": {"units": SampleUnit.MILLIMETERS}},
                "scale_fits": (fit,),
            }
        )
    )
    plan = build_execution_plan(
        request=ProcessingRequest(
            sensor_groups=("mocap",), start_stage=ProcessingStage.RECONSTRUCTION
        ),
        metadata=RecordingMetadata(
            recording_id="recording", selected_run_id=0, runs={0: base}
        ),
        signatures={"mocap": {stage: stage.value for stage in STAGE_ORDER}},
        inputs={"mocap": CameraExecutionInputs(camera_ids=(), geometry=())},
    )
    assert retained_run(base=base, plan=plan).scale_fits == (fit,)


def test_triangulation_restart_preserves_detection_and_invalidates_3d() -> None:
    plan = build_execution_plan(
        inputs={"mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())},
        request=ProcessingRequest(
            sensor_groups=("mocap",), start_stage=ProcessingStage.TRIANGULATION
        ),
        metadata=metadata_fixture(),
        signatures={"mocap": {stage: stage.value for stage in STAGE_ORDER}},
    )
    assert ProcessingStage.OBSERVATIONS not in plan.invalidate
    assert ProcessingStage.TIMING not in plan.invalidate
    assert ProcessingStage.TRIANGULATION in plan.execute
    assert ProcessingStage.RECONSTRUCTION in plan.invalidate


def test_independent_stage_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="stop_stage must depend"):
        build_execution_plan(
            inputs={
                "mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())
            },
            request=ProcessingRequest(
                sensor_groups=("mocap",),
                start_stage=ProcessingStage.BIOMECHANICS,
                stop_stage=ProcessingStage.REPROJECTION,
            ),
            metadata=metadata_fixture(),
            signatures={"mocap": {stage: stage.value for stage in STAGE_ORDER}},
        )


def test_saved_reconstruction_needs_only_direct_inputs() -> None:
    metadata = metadata_fixture()
    required = (ProcessingStage.FILTERING, ProcessingStage.SCALE_FIT)
    run = metadata.runs[0].model_copy(
        update={
            "checkpoints": tuple(
                checkpoint
                for checkpoint in metadata.runs[0].checkpoints
                if checkpoint.stage in required
            )
        }
    )
    metadata = metadata.model_copy(update={"runs": {0: run}})
    plan = build_execution_plan(
        request=ProcessingRequest(
            sensor_groups=("mocap",),
            start_stage=ProcessingStage.RECONSTRUCTION,
            stop_stage=ProcessingStage.RECONSTRUCTION,
        ),
        metadata=metadata,
        signatures={"mocap": {stage: stage.value for stage in required}},
        inputs={"mocap": CameraExecutionInputs(camera_ids=(), geometry=())},
    )
    assert plan.execute == (ProcessingStage.RECONSTRUCTION,)
    assert ProcessingStage.REPROJECTION in plan.invalidate


@pytest.mark.parametrize(
    "stage,cameras,requires_geometry",
    [
        (ProcessingStage.TRIANGULATION, ("one",), False),
        (ProcessingStage.TRIANGULATION, ("one", "two"), True),
        (ProcessingStage.REPROJECTION, ("one",), True),
        (ProcessingStage.FILTERING, ("one", "two"), False),
        (ProcessingStage.BIOMECHANICS, (), False),
    ],
)
def test_geometry_required_only_by_executed_operation(
    stage: ProcessingStage,
    cameras: tuple[str, ...],
    requires_geometry: bool,
) -> None:
    request = ProcessingRequest(
        sensor_groups=("mocap",), start_stage=stage, stop_stage=stage
    )
    inputs = {"mocap": CameraExecutionInputs(camera_ids=cameras, geometry=())}
    signatures = {"mocap": {item: item.value for item in STAGE_ORDER}}
    if requires_geometry:
        with pytest.raises(ValueError, match="requires resolved camera geometry"):
            build_execution_plan(
                request=request,
                metadata=metadata_fixture(),
                signatures=signatures,
                inputs=inputs,
            )
    else:
        assert build_execution_plan(
            request=request,
            metadata=metadata_fixture(),
            signatures=signatures,
            inputs=inputs,
        ).execute == (stage,)


def metadata_fixture() -> RecordingMetadata:
    groups = {
        "mocap": SensorGroup(clock_description="capture clock", sample_count=2),
        "eye": SensorGroup(clock_description="mapped device clock", sample_count=8),
    }
    channels = tuple(
        Channel(
            sensor_group=group,
            source="human",
            reference_frame="world",
            kind="LANDMARKS_3D",
            names=("left_wrist",),
            components={"x": "mm", "y": "mm", "z": "mm"},
            stage=ProcessingStage.RECONSTRUCTION,
        )
        for group in groups
    )
    run = RunDescriptor(
        sensor_groups=groups,
        sources={"human": Source(kind="instance", definition={"instance_id": 0})},
        reference_frames={"world": {"up": "+z"}},
        models={},
        processing={},
        channels=channels,
        checkpoints=tuple(
            StageCheckpoint(sensor_group=group, stage=stage, signature=stage.value)
            for group in groups
            for stage in STAGE_ORDER
        ),
    )
    return RecordingMetadata(recording_id="recording", selected_run_id=0, runs={0: run})


def sample_batch(*, group: str, count: int, fps: float) -> pa.RecordBatch:
    rows: list[dict[str, object]] = []
    for frame in range(count):
        for component in ("x", "y", "z"):
            rows.append(
                dict(
                    timestamp_s=frame / fps,
                    sensor_group=group,
                    frame_number=frame,
                    source="human",
                    reference_frame="world",
                    channel="LANDMARKS_3D",
                    name="left_wrist",
                    component=component,
                    value=None if frame == 1 else 1.0,
                    units="mm",
                    run_id=0,
                )
            )
    return pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)


def test_mixed_rates_and_missing_components_round_trip(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = metadata_fixture()
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
    assert read_metadata(path=structure.data_parquet_path) == metadata
    eye = pa.Table.from_batches(
        list(
            read_batches(
                path=structure.data_parquet_path, run_id=0, sensor_groups=("eye",)
            )
        )
    )
    assert eye.num_rows == 24
    assert eye.column("value").null_count == 3
    assert eye.column("timestamp_s")[6].as_py() == 2 / 120
    structure.recording_info_path.write_text(
        "interrupted JSON publication", encoding="utf-8"
    )
    assert repair_metadata_mirror(structure=structure) == metadata
    assert (
        RecordingMetadata.model_validate_json(
            structure.recording_info_path.read_text(encoding="utf-8")
        )
        == metadata
    )


def test_failed_write_preserves_completed_recording(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = metadata_fixture()
    batches = [
        sample_batch(group="mocap", count=2, fps=30.0),
        sample_batch(group="eye", count=8, fps=120.0),
    ]
    with recording_write_lock(structure=structure):
        publish_recording(structure=structure, metadata=metadata, batches=batches)
        before = structure.data_parquet_path.read_bytes()
        with pytest.raises(ValueError, match="Incomplete"):
            publish_recording(
                structure=structure, metadata=metadata, batches=batches[:1]
            )
        assert structure.data_parquet_path.read_bytes() == before
        with pytest.raises(ValueError, match="Duplicate"):
            publish_recording(
                structure=structure, metadata=metadata, batches=[batches[0], batches[0]]
            )
        assert structure.data_parquet_path.read_bytes() == before


def test_keep_and_stop_invalidate_only_selected_group() -> None:
    metadata = metadata_fixture()
    request = ProcessingRequest(
        keep=True,
        sensor_groups=("mocap",),
        start_stage=ProcessingStage.FILTERING,
        stop_stage=ProcessingStage.FILTERING,
    )
    signatures = {"mocap": {stage: stage.value for stage in STAGE_ORDER}}
    plan = build_execution_plan(
        inputs={"mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())},
        request=request,
        metadata=metadata,
        signatures=signatures,
    )
    assert plan.target_run_id == 1
    assert plan.execute == (ProcessingStage.FILTERING,)
    retained = retained_run(base=metadata.runs[0], plan=plan)
    assert [channel.sensor_group for channel in retained.channels] == ["eye"]
    assert len(metadata.runs[0].channels) == 2
    signatures["mocap"][ProcessingStage.TRIANGULATION] = "changed 3D input"
    with pytest.raises(ValueError, match="Restart at triangulation"):
        build_execution_plan(
            inputs={
                "mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())
            },
            request=request,
            metadata=metadata,
            signatures=signatures,
        )


def test_recording_lock_rejects_concurrent_writer(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        with pytest.raises(Timeout):
            with recording_write_lock(structure=structure):
                pytest.fail("Concurrent writer entered")


def test_keep_then_overwrite_publishes_independent_runs(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = metadata_fixture()
    signatures = {"mocap": {stage: stage.value for stage in STAGE_ORDER}}
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
        plan = build_execution_plan(
            inputs={
                "mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())
            },
            metadata=metadata,
            signatures=signatures,
            request=ProcessingRequest(
                keep=True,
                sensor_groups=("mocap",),
                start_stage=ProcessingStage.FILTERING,
                stop_stage=ProcessingStage.FILTERING,
            ),
        )
        result = retained_run(base=metadata.runs[0], plan=plan)
        kept = publish_checkpoint(
            structure=structure,
            metadata=metadata,
            plan=plan,
            result=result,
            computed_batches=[],
        )
        assert set(kept.runs) == {0, 1}
        assert (
            sum(
                batch.num_rows
                for batch in read_batches(
                    path=structure.data_parquet_path, run_id=0, sensor_groups=("mocap",)
                )
            )
            == 6
        )
        assert (
            list(
                read_batches(
                    path=structure.data_parquet_path, run_id=1, sensor_groups=("mocap",)
                )
            )
            == []
        )
        assert (
            sum(
                batch.num_rows
                for batch in read_batches(
                    path=structure.data_parquet_path, run_id=1, sensor_groups=("eye",)
                )
            )
            == 24
        )
        overwrite_plan = build_execution_plan(
            inputs={
                "mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())
            },
            metadata=kept,
            signatures=signatures,
            request=ProcessingRequest(
                sensor_groups=("mocap",),
                start_stage=ProcessingStage.FILTERING,
                stop_stage=ProcessingStage.FILTERING,
            ),
        )
        overwritten = publish_checkpoint(
            structure=structure,
            metadata=kept,
            plan=overwrite_plan,
            result=retained_run(base=kept.runs[0], plan=overwrite_plan),
            computed_batches=[],
        )
        assert set(overwritten.runs) == {0, 1}
        assert overwritten.runs[1] == kept.runs[1]
        assert (
            list(
                read_batches(
                    path=structure.data_parquet_path, run_id=0, sensor_groups=("mocap",)
                )
            )
            == []
        )


def test_static_measurement_round_trip_and_expansion(tmp_path: Path) -> None:
    metadata = metadata_fixture()
    values = {"upper_arm": {"length_mm": 301.0}}
    static = StaticChannel(
        channel=Channel(
            sensor_group="mocap",
            source="human",
            reference_frame=None,
            kind="SEGMENT_LENGTHS",
            names=("upper_arm",),
            components={"length_mm": "mm"},
            stage=ProcessingStage.SCALE_FIT,
        ),
        values=values,
    )
    run_data = metadata.runs[0].model_dump()
    run_data["static_channels"] = [static.model_dump()]
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=0,
        runs={0: RunDescriptor.model_validate(run_data)},
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
    loaded = read_metadata(path=structure.data_parquet_path).runs[0].static_channels[0]
    assert loaded == static
    expanded = static_samples(
        channel=loaded, run_id=0, frame_number=1, timestamp_s=1 / 30
    )
    assert expanded.column("value").to_pylist() == [301.0]
    assert expanded.column("reference_frame").null_count == 1


def test_kept_recomputed_values_do_not_change_base_run(tmp_path: Path) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = metadata_fixture()
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=[
                sample_batch(group="mocap", count=2, fps=30.0),
                sample_batch(group="eye", count=8, fps=120.0),
            ],
        )
        plan = build_execution_plan(
            inputs={
                "mocap": CameraExecutionInputs(camera_ids=("camera",), geometry=())
            },
            request=ProcessingRequest(
                keep=True,
                sensor_groups=("mocap",),
                start_stage=ProcessingStage.RECONSTRUCTION,
                stop_stage=ProcessingStage.RECONSTRUCTION,
            ),
            metadata=metadata,
            signatures={"mocap": {stage: stage.value for stage in STAGE_ORDER}},
        )
        data = retained_run(base=metadata.runs[0], plan=plan).model_dump()
        data["channels"] = (
            *data["channels"],
            metadata.runs[0].channels[0].model_dump(),
        )
        data["checkpoints"] = (
            *data["checkpoints"],
            StageCheckpoint(
                sensor_group="mocap",
                stage=ProcessingStage.RECONSTRUCTION,
                signature="recomputed",
            ).model_dump(),
        )
        samples = sample_batch(group="mocap", count=2, fps=30.0).to_pydict()
        samples["run_id"] = [1] * 6
        samples["value"] = [12.0] * 6
        publish_checkpoint(
            structure=structure,
            metadata=metadata,
            plan=plan,
            result=RunDescriptor.model_validate(data),
            computed_batches=[
                pa.RecordBatch.from_pydict(samples, schema=SAMPLE_SCHEMA)
            ],
        )
    base_values = [
        value
        for batch in read_batches(
            path=structure.data_parquet_path, run_id=0, sensor_groups=("mocap",)
        )
        for value in batch.column("value").to_pylist()
    ]
    kept_values = [
        value
        for batch in read_batches(
            path=structure.data_parquet_path, run_id=1, sensor_groups=("mocap",)
        )
        for value in batch.column("value").to_pylist()
    ]
    assert base_values == [1.0, 1.0, 1.0, None, None, None]
    assert kept_values == [12.0] * 6


@pytest.mark.parametrize(
    "column,value,error",
    [
        ("units", "px", "incorrect units"),
        ("timestamp_s", 0.0001, "Inconsistent"),
        ("value", float("inf"), "finite"),
        ("value", float("nan"), "finite"),
    ],
)
def test_invalid_samples_fail_before_publication(
    tmp_path: Path, column: str, value: object, error: str
) -> None:
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    batch = sample_batch(group="mocap", count=2, fps=30.0)
    columns = batch.to_pydict()
    columns[column][0] = value
    invalid = pa.RecordBatch.from_pydict(columns, schema=SAMPLE_SCHEMA)
    with recording_write_lock(structure=structure):
        with pytest.raises(ValueError, match=error):
            publish_recording(
                structure=structure,
                metadata=metadata_fixture(),
                batches=[invalid, sample_batch(group="eye", count=8, fps=120.0)],
            )
    assert not structure.data_parquet_path.exists()


@pytest.mark.parametrize(
    "quaternion",
    [
        (1.0, 0.0, 0.0, 0.0),
        (None, None, None, None),
        (2.0, 0.0, 0.0, 0.0),
        (1.0, None, 0.0, 0.0),
    ],
)
def test_quaternion_components_span_batches(
    tmp_path: Path, quaternion: tuple[float | None, ...]
) -> None:
    fixture = metadata_fixture()
    run_data = fixture.runs[0].model_dump()
    run_data["sensor_groups"] = {
        "mocap": SensorGroup(
            clock_description="capture clock", sample_count=1
        ).model_dump()
    }
    run_data["checkpoints"] = []
    run_data["channels"] = [
        Channel(
            sensor_group="mocap",
            source="human",
            reference_frame="world",
            kind="ROTATIONS_WORLD",
            names=("arm",),
            components={"w": "1", "x": "1", "y": "1", "z": "1"},
            stage=ProcessingStage.RECONSTRUCTION,
        ).model_dump()
    ]
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=0,
        runs={0: RunDescriptor.model_validate(run_data)},
    )
    rows: list[dict[str, object]] = [
        dict(
            timestamp_s=0.0,
            sensor_group="mocap",
            frame_number=0,
            source="human",
            reference_frame="world",
            channel="ROTATIONS_WORLD",
            name="arm",
            component=component,
            value=value,
            units="1",
            run_id=0,
        )
        for component, value in zip(("w", "x", "y", "z"), quaternion, strict=True)
    ]
    batch = pa.RecordBatch.from_pylist(rows, schema=SAMPLE_SCHEMA)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        if quaternion in ((1.0, 0.0, 0.0, 0.0), (None, None, None, None)):
            publish_recording(
                structure=structure,
                metadata=metadata,
                batches=[batch.slice(0, 2), batch.slice(2)],
            )
            assert (
                sum(
                    item.num_rows
                    for item in read_batches(
                        path=structure.data_parquet_path,
                        run_id=0,
                        sensor_groups=("mocap",),
                    )
                )
                == 4
            )
        else:
            with pytest.raises(ValueError, match="Quaternion"):
                publish_recording(
                    structure=structure, metadata=metadata, batches=[batch]
                )
