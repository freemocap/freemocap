"""Changed camera geometry is exported once; original calibrations stay intact."""
from concurrent.futures import ThreadPoolExecutor
from math import cos, sin

import pytest
import numpy as np
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition

from freemocap.core.tasks.calibration.shared.calibration_exports import save_aligned_calibration
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.calibration.shared.calibration_transform import CalibrationTransform
from freemocap.core.tasks.calibration.shared.camera_model import CameraModel
from freemocap.core.tasks.calibration.shared.camera_intrinsics import CameraIntrinsics
from freemocap.core.tasks.calibration.shared.camera_extrinsics import CameraExtrinsics


@pytest.fixture
def calibration(tmp_path):
    source = CalibrationResult(cameras=[CameraModel(id='camera0', index=0, image_size=(1280, 720),
        intrinsics=CameraIntrinsics(fx=900., fy=920., cx=640., cy=360.),
        extrinsics=CameraExtrinsics(quaternion_wxyz=[1., 0., 0., 0.], translation=[0., 0., 0.]))],
        board=CharucoBoardDefinition.create_letter_size_5x3(), reprojection_error_px=0.,
        initial_cost=0., final_cost=0., n_iterations=1, time_seconds=0.,
        n_observations_used=100, n_observations_rejected=0)
    path = tmp_path / 'room_calibration.toml'
    source.save_toml(path)
    return dict(source_path=path, source=source, recording_path=tmp_path / 'recording', recording_id='recording')


def transform(distance):
    return (CalibrationTransform(operation='manual', quaternion_wxyz=(1., 0., 0., 0.),
                                 translation_mm=(distance, 0., 0.)),)


def test_unchanged_calibration_creates_no_export(calibration):
    assert save_aligned_calibration(**calibration, transformations=()) is None
    assert save_aligned_calibration(**calibration, transformations=transform(0.)) is None
    assert not calibration['recording_path'].exists()


def test_changed_calibration_reuses_identical_export_and_preserves_source(calibration):
    original = calibration['source_path'].read_bytes()
    saved = save_aligned_calibration(**calibration, transformations=transform(10.))
    assert saved.parent == calibration['recording_path'] / 'exports' / 'calibration_copies'
    assert saved.name.startswith('room_calibration__aligned__')
    assert CalibrationResult.load_toml(saved).cameras != calibration['source'].cameras
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save_aligned_calibration(**calibration, transformations=transform(10.)), range(2)))
    assert results == [saved, saved]
    changed = save_aligned_calibration(**calibration, transformations=transform(20.))
    assert changed != saved
    assert len(list(saved.parent.glob('*.toml'))) == 2
    assert calibration['source_path'].read_bytes() == original


def test_rotated_calibration_preserves_transform_history(calibration):
    transformations = (CalibrationTransform(operation='manual',
        quaternion_wxyz=(cos(.31), 0., sin(.31), 0.), translation_mm=(1.2, -3.4, 5.6)),)
    saved = save_aligned_calibration(**calibration, transformations=transformations)
    expected = calibration['source'].transformed(transformations=transformations, recording_id='recording')
    loaded = CalibrationResult.load_toml(saved)
    assert loaded.to_metadata().model_dump(mode='json') == expected.to_metadata().model_dump(mode='json')
    np.testing.assert_allclose(loaded.cameras[0].extrinsics.rotation_matrix,
                               expected.cameras[0].extrinsics.rotation_matrix, atol=1e-14, rtol=0.)
    np.testing.assert_array_equal(loaded.cameras[0].extrinsics.translation, expected.cameras[0].extrinsics.translation)
    assert save_aligned_calibration(**calibration, transformations=transformations) == saved


def test_run_calibration_copy_stays_in_run_folder(calibration):
    original = save_aligned_calibration(**calibration, transformations=transform(10.))
    kept = save_aligned_calibration(**calibration, transformations=transform(10.), run_id=2)
    assert kept.parent.parent.name == 'run-2'
    assert kept.name.endswith('.run-2.toml')
    assert original.is_file()
    assert save_aligned_calibration(**calibration, transformations=transform(10.), run_id=2) == kept
