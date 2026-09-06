"""Saved geometry preserves the projection used by triangulation."""

import numpy as np
from pathlib import Path

from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import publish_recording, recording_write_lock
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata
from freemocap.core.pipeline.posthoc.execution_inputs import CameraExecutionInputs
from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.test_recording_store import metadata_fixture, sample_batch

from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel


def test_camera_geometry_json_round_trip_preserves_projection(tmp_path: Path) -> None:
    camera = CameraModel(
        id="camera",
        index=0,
        image_size=(640, 480),
        intrinsics=CameraIntrinsics(fx=800.0, fy=810.0, cx=320.0, cy=240.0, k1=0.01),
        extrinsics=CameraExtrinsics(
            quaternion_wxyz=np.array([1.0, 0.0, 0.0, 0.0]),
            translation=np.array([100.0, 20.0, 500.0]),
        ),
    )
    descriptor = camera.model_copy(deep=True)
    restored = CameraModel.model_validate_json(
        descriptor.model_dump_json()
    )
    np.testing.assert_allclose(restored.projection_matrix, camera.projection_matrix)
    np.testing.assert_allclose(
        restored.intrinsics.to_dist_coeffs_5(), camera.intrinsics.to_dist_coeffs_5()
    )
    np.testing.assert_allclose(
        restored.world_position, camera.world_position
    )
    np.testing.assert_allclose(restored.world_orientation, camera.world_orientation)
    assert restored == camera
    assert CameraModel.model_json_schema()
    assert RecordingMetadata.model_json_schema()
    CameraExecutionInputs(camera_ids=(camera.id,), geometry=(camera,)).validate_for((ProcessingStage.REPROJECTION,))
    metadata = metadata_fixture()
    metadata.runs[0].camera_geometry["mocap"] = (camera,)
    structure = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    with recording_write_lock(structure=structure):
        publish_recording(
            structure=structure, metadata=metadata,
            batches=[sample_batch(group="mocap", count=2, fps=30.0), sample_batch(group="eye", count=8, fps=120.0)],
        )
    loaded = read_metadata(path=structure.data_parquet_path)
    assert loaded == metadata
    assert isinstance(loaded.runs[0].camera_geometry["mocap"][0], CameraModel)
    np.testing.assert_allclose(loaded.runs[0].camera_geometry["mocap"][0].projection_matrix, camera.projection_matrix)
    camera.extrinsics.translation[0] = -1000.0
    assert descriptor.extrinsics.translation[0] == 100.0
