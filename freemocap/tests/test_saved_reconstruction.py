"""Saved numeric input selection rejects incomplete streams and fingerprints actual inputs."""

from dataclasses import replace
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from pathlib import Path

import numpy as np
from numpy import testing as npt
import pyarrow.parquet as pq
import pytest
from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_board_definition import (
    CharucoBoardDefinition,
)

from freemocap.core.recording.channel_series import SeriesSampling
from freemocap.core.recording.input_signatures import (
    definition_signature,
    point_array_signature,
)
from freemocap.core.recording.recorded_model import RecordedModel
from freemocap.core.recording.recording_metadata import (
    RecordingMetadata,
    RunDescriptor,
    SensorGroup,
    Source,
    SourceKind,
)
from freemocap.core.recording.recording_scale_fit import RecordingScaleFit
from freemocap.core.recording.recording_writer import (
    publish_recording,
    recording_write_lock,
)
from freemocap.core.recording.saved_reconstruction import (
    SavedPointPolicy,
    SavedReconstructionRequest,
    read_saved_reconstruction,
)
from freemocap.core.recording.spatial_point_series import (
    PointSeriesDefinition,
    SpatialPointSeries,
    SpatialReference,
)
from freemocap.core.skeletons.charuco_board_skeleton import build_charuco_board_bundle
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture
def saved_request(tmp_path: Path) -> SavedReconstructionRequest:
    bundle = build_charuco_board_bundle(
        board=CharucoBoardDefinition.create_letter_size_5x3()
    )
    reference = SpatialReference.for_camera_count(1)
    series = SpatialPointSeries(
        definition=PointSeriesDefinition(
            sensor_group="mocap",
            source=bundle.detector_type,
            names=bundle.tracker_keypoint_names,
            reference=reference,
        ),
        values=np.full((2, len(bundle.tracker_keypoint_names), 3), np.nan),
    )
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    metadata = RecordingMetadata(
        recording_id="recording",
        selected_run_id=3,
        runs={
            3: RunDescriptor(
                sensor_groups={
                    "mocap": SensorGroup(
                        clock_description="recording clock", sample_count=2
                    )
                },
                sources={
                    bundle.detector_type: Source(
                        kind=SourceKind.TRACKER, definition={}
                    ),
                    bundle.model_id: Source(kind=SourceKind.INSTANCE, definition={}),
                },
                reference_frames={reference.name: reference.model_dump(mode="json")},
                models={bundle.model_id: RecordedModel.from_bundle(bundle)},
                processing={},
                channels=(series.definition.to_channel(),),
                scale_fits=(
                    RecordingScaleFit(
                        inputs=RecordingFitInputs.from_points(
                            names=series.definition.names,
                            values=series.values,
                            model=RecordedModel.from_bundle(bundle),
                        ),
                        sensor_group="mocap",
                        source=bundle.model_id,
                        reference_frame=reference.name,
                        units=reference.units,
                        fit=None,
                    ),
                ),
            )
        },
    )
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure,
            metadata=metadata,
            batches=series.batches(
                SeriesSampling(
                    frame_numbers=(10, 11),
                    timestamps_s=(1.0, 1.07),
                    run_id=3,
                    batch_size=5,
                )
            ),
        )
    return SavedReconstructionRequest(
        structure=structure,
        run_id=3,
        sensor_group="mocap",
        point_source=bundle.detector_type,
        model_id=bundle.model_id,
        point_policy=SavedPointPolicy.IDENTITY,
        compute_center_of_mass=False,
    )


def test_null_points_and_absent_fit_survive_rebatching(
    saved_request: SavedReconstructionRequest,
) -> None:
    loaded = read_saved_reconstruction(saved_request)
    assert loaded.fit.fit is None
    assert np.isnan(loaded.points.values).all()
    assert loaded.points.frames == (10, 11)
    assert loaded.points.timestamps_s == (1.0, 1.07)
    assert not loaded.points.values.flags.writeable
    path = saved_request.structure.data_parquet_path
    table = pq.read_table(path)
    pq.write_table(table, path, row_group_size=7)
    replay = read_saved_reconstruction(saved_request)
    assert replay.signatures == loaded.signatures
    npt.assert_array_equal(replay.points.values, loaded.points.values)
    changed = read_saved_reconstruction(
        replace(saved_request, compute_center_of_mass=True)
    )
    assert changed.signatures.points == loaded.signatures.points
    assert changed.signatures.reconstruction != loaded.signatures.reconstruction


def test_truncated_points_fail(saved_request: SavedReconstructionRequest) -> None:
    path = saved_request.structure.data_parquet_path
    table = pq.read_table(path)
    pq.write_table(table.slice(0, table.num_rows - 1), path)
    with pytest.raises(ValueError):
        read_saved_reconstruction(saved_request)


def test_wrong_group_fails(saved_request: SavedReconstructionRequest) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        read_saved_reconstruction(replace(saved_request, sensor_group="eye"))


def test_point_fingerprint_tracks_values_shape_and_missingness() -> None:
    values = np.array([[[0.0, np.nan, 2.0]]])
    signature = point_array_signature(values)
    same = values.copy()
    same.view(np.uint64)[0, 0, 1] = 0x7FF8000000000001
    assert point_array_signature(same) == signature
    same[0, 0, 1] = 0.0
    assert point_array_signature(same) != signature
    assert point_array_signature(values.reshape(3, 1, 1)) != signature
    same[0, 0, 2] = 3.0
    assert point_array_signature(same) != signature
    same[0, 0, 0] = np.inf
    with pytest.raises(ValueError, match="infinity"):
        point_array_signature(same)


def test_definition_fingerprint_canonicalizes_sets_and_rejects_nonfinite() -> None:
    assert definition_signature(frozenset({"a", "b"})) == definition_signature(
        {"b", "a"}
    )
    assert definition_signature(dict(scale=1.0)) != definition_signature(
        dict(scale=2.0)
    )
    with pytest.raises(ValueError):
        definition_signature(dict(scale=np.inf))
