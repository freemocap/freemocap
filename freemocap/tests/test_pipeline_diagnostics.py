"""Diagnostics retain rejected evidence and use independent length references."""

import cbor2
import numpy as np
import pyarrow as pa
import pytest
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import ResidualAccumulator
from skellytracker.core.data_primitives.keypoints import Keypoints
from skellytracker.core.data_primitives.observation import Observation, StageObservation

from freemocap.core.diagnostics.pipeline_diagnostics import frame_diagnostics
from freemocap.core.recording.sample_encoding.diagnostic_samples import reprojection_series
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.tasks.triangulation.helpers.reprojection_diagnostics import NamedReprojectionDiagnostics
from freemocap.core.reconstruction.posthoc_reconstruction import triangulate_observation_buffers, reconstruct_skeletons_for_recording
from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import build_reconstruction_states, streaming_model_scale_source
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.streaming.message_model import FrameMessage, encode_message
from freemocap.core.tasks.triangulation.helpers.project_single_camera import project_2d_batch_to_3d
from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.triangulation.triangulator import Triangulator
from freemocap.core.tracking.observation_buffer import ObservationBuffer
from freemocap.tests.calibration.test_calibration_state_latch import build_loaded_tracker
from freemocap.tests.calibration.test_matching_fitness import camera_rig, observations
from freemocap.tests.calibration.test_posthoc_matching import recorded_request
from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints


def test_triangulator_retains_unreconstructable_observations_and_units() -> None:
    cameras = camera_rig()
    pixels = observations(cameras)[:, 0]
    pixels[1:, 0] = np.nan
    result = Triangulator(cameras=list(cameras)).triangulate(data2d=pixels, config=TriangulationConfig(use_outlier_rejection=False))
    diagnostics = result.diagnostics
    assert diagnostics is not None and diagnostics.units == 'pixels'
    assert diagnostics.observed[:, 0].tolist() == [True, False, False]
    assert not diagnostics.reconstructed[:, 0].any()
    np.testing.assert_allclose(diagnostics.errors, result.reprojection_error)
    assert diagnostics.summaries()[0].observed_count == 10
    assert diagnostics.summaries()[0].reconstructed_count == 9
    result.points_3d[:] = np.nan
    assert diagnostics.reconstructed[:, 1:].all()
    assert project_2d_batch_to_3d(data2d=pixels[0][None]).diagnostics is None


def test_live_gate_keeps_errors_and_qualified_point_identity() -> None:
    tracker = build_loaded_tracker()
    assert tracker.calibration is not None
    cameras = tracker.calibration.cameras
    source_ids = tuple(camera.id for camera in cameras)
    tracker.bind_live_cameras(live_camera_indices={name: index for index, name in enumerate(source_ids)})
    xyz = np.array([[0., 0., 3000.], [100., 50., 3000.]])
    pixels = tracker.triangulator.project(xyz)
    pixels[0, 1] += [80., 60.]
    observations_by_source: dict[str, Observation] = {}
    for index, source in enumerate(source_ids):
        order = [1, 0] if index == 1 else [0, 1]
        observations_by_source[source] = Observation(frame_number=0, image_size=(720, 1280), stages={
            'body': StageObservation(name='body', keypoints=Keypoints(
                names=tuple(('clean', 'corrupt')[point] for point in order),
                xyz=np.column_stack((pixels[index, order], np.zeros(2))), visibility=np.ones(2),
            )),
        })
    result = tracker.try_angulate(frame_number=0, frame_observations_by_camera=observations_by_source,
                                 max_reprojection_error_px=1., triangulation_config=TriangulationConfig(use_outlier_rejection=False))
    assert result is not None and result.diagnostics is not None
    assert 'clean' in result.points and 'corrupt' not in result.points
    assert result.diagnostics.point_names == ('body.clean', 'body.corrupt')
    assert result.diagnostics.source_ids == source_ids
    assert np.isfinite(result.diagnostics.values.errors[:, 1]).all()
    payload = frame_diagnostics(reprojection=(result.diagnostics,), reconstructions={}, length_units='millimeters')
    decoded = cbor2.loads(encode_message(FrameMessage(frame_number=0, diagnostics=payload)))
    block = decoded['diagnostics']['reprojection'][0]
    packed = np.frombuffer(block['data'], dtype='<f4').reshape(len(source_ids), 2, 4)
    np.testing.assert_allclose(packed[..., 0], result.diagnostics.values.errors, rtol=1e-6, atol=1e-6)


def test_rigid_residual_uses_reference_before_live_fit_update() -> None:
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    state = build_reconstruction_states(bundles=(bundle,), scale_source_for=streaming_model_scale_source(window_frames=30))[bundle.model_id]
    points = _standing_keypoints()
    first = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=False)
    assert first is not None
    assert all(reading.reference_length is None and reading.residual is None for reading in first.rigid_body_residuals.values())
    second = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints={name: point * 1.1 for name, point in points.items()}, compute_center_of_mass=False)
    assert second is not None
    measured = [name for name, reading in second.rigid_body_residuals.items() if reading.measured_length is not None]
    assert measured
    for name in measured:
        reading = second.rigid_body_residuals[name]
        assert reading.reference_kind == 'prior_live_fit'
        assert reading.reference_length == first.segment_lengths[name]
        assert reading.residual == pytest.approx(reading.measured_length - first.segment_lengths[name])
    state.reset()
    reset = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=points, compute_center_of_mass=False)
    assert reset is not None and all(reading.reference_length is None for reading in reset.rigid_body_residuals.values())


def test_recording_channels_retain_full_diagnostic_arrays() -> None:
    request = recorded_request()
    buffers = {source: ObservationBuffer() for source in request.videos}
    for frame in request.frames:
        for source, observation in frame.items():
            buffers[source].add_observation(observation)
    geometry = request.resolve(result=request.evaluate())
    result = triangulate_observation_buffers(observation_buffers=buffers, camera_geometry=geometry,
        triangulation_config=TriangulationConfig(use_outlier_rejection=False), max_reprojection_error_px=None, timing=PosthocTimingReport())
    assert result.reconstruction.diagnostics is not None
    diagnostics = NamedReprojectionDiagnostics(source_ids=result.sources, point_names=result.diagnostic_point_names,
        values=result.reconstruction.diagnostics)
    series = tuple(reprojection_series(diagnostics=diagnostics, sensor_group='mocap'))
    for camera_index, camera in enumerate(result.sources):
        error_series = series[camera_index * 3]
        assert error_series.channel.source == f'camera:{camera}'
        assert error_series.channel.names == result.diagnostic_point_names
        table = pa.Table.from_batches(list(error_series.batches(SeriesSampling(
            frame_numbers=tuple(range(len(request.frames))), timestamps_s=tuple(index / 30 for index in range(len(request.frames))), run_id=0))))
        np.testing.assert_allclose(table['value'].to_numpy().reshape(error_series.values.shape)[..., 0], result.reconstruction.reprojection_error[camera_index])


def test_online_residual_statistics_preserve_missing_measurements() -> None:
    accumulator = ResidualAccumulator()
    for value in (1., None, 3.):
        accumulator.add(residual=value)
    summary = accumulator.summary()
    assert summary.sample_count == 2 and summary.unavailable_count == 1
    assert summary.mean == 2. and summary.standard_deviation == 1.
    assert summary.rms == pytest.approx(np.sqrt(5.))
    with pytest.raises(ValueError, match='finite'):
        accumulator.add(residual=float('nan'))


def test_posthoc_residuals_use_one_frozen_fit_and_do_not_invent_missing_measurements() -> None:
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    points = _standing_keypoints()
    values = np.stack(list(points.values()))
    result = reconstruct_skeletons_for_recording(request=RecordingReconstructionInput(
        bundles=(bundle,), keypoint_names=tuple(points),
        keypoints_3d=np.stack((values, values * 1.1, np.full_like(values, np.nan))),
        compute_center_of_mass=False, timing=PosthocTimingReport(),
    ))[bundle.model_id]
    assert result.scale_fit is not None and result.frames[2] is None
    for frame in result.frames[:2]:
        assert frame is not None
        for name, reading in frame.rigid_body_residuals.items():
            assert reading.reference_kind == 'recording_fit'
            assert reading.reference_length == result.scale_fit.segment_lengths[name]
            if reading.measured_length is None:
                assert reading.residual is None
