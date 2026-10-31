"""Weighted placement changes only standard-human translations and their products."""
from dataclasses import replace

import numpy as np

from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit
from skellyforge.core.skeleton.pose.pose_tensor import PoseTensor
from freemocap.core.reconstruction.recording_pose_outputs import RecordingPoseOutputs
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.types.channel_kind import ChannelKind


def pose_fixture():
    bundle = build_standard_human_bundle(detector_type="rtmpose")
    names = tuple(bundle.skeleton.segments)
    scales = dict.fromkeys(names, 1700.)
    fit = ModelScaleFit(fitted_scale=1700., segment_scales=scales,
        segment_lengths={n: s.length * scales[n] for n, s in bundle.skeleton.segments.items()},
        measured_segment_names=frozenset(names), voting_segment_names=frozenset(names))
    rng = np.random.default_rng(26)
    shape = 4, len(names)
    present = np.ones(shape, dtype=bool)
    present[1, names.index("thoracic")] = False
    present[2] = False
    origins = rng.normal(size=(*shape, 3)) * 400
    rotations = rng.normal(size=(*shape, 4))
    rotations /= np.linalg.norm(rotations, axis=-1, keepdims=True)
    origins[~present] = np.nan
    rotations[~present] = np.nan
    poses = PoseTensor(names, origins, rotations, np.where(present, 1700., np.nan),
                       present.astype(np.uint8), present.astype(np.uint8))
    return bundle, fit, poses


def calculate_channels(outputs, poses):
    landmarks = outputs.landmark_names
    result = outputs.calculate(poses=poses, landmark_names=landmarks,
        landmark_positions=np.zeros((poses.sample_count, len(landmarks), 3)),
        landmark_present=np.ones((poses.sample_count, len(landmarks)), dtype=bool), start_position=0)
    return {tensor.tensor_layout.channel_kind: tensor for tensor in result}


def test_rotations_lengths_masks_layouts_and_source_observations_match_connected_baseline():
    bundle, fit, poses = pose_fixture()
    weighted = RecordingPoseOutputs(bundle=bundle, fit=fit, compute_center_of_mass=True)
    baseline = RecordingPoseOutputs(bundle=bundle, fit=fit, compute_center_of_mass=True)
    baseline.weighted_attachments = None
    actual, expected = calculate_channels(weighted, poses), calculate_channels(baseline, poses)
    changed = {ChannelKind.SEGMENT_ORIGINS, ChannelKind.LANDMARKS_3D, ChannelKind.DERIVED_POINTS}
    assert actual.keys() == expected.keys()
    for kind in actual:
        assert actual[kind].tensor_layout == expected[kind].tensor_layout
        np.testing.assert_array_equal(actual[kind].companion_values("entry_presence"), expected[kind].companion_values("entry_presence"))
        if kind not in changed:
            np.testing.assert_array_equal(actual[kind].data_values, expected[kind].data_values)
    assert weighted.fit is fit
    np.testing.assert_array_equal(weighted.positions.landmark_vectors, baseline.positions.landmark_vectors)
    np.testing.assert_array_equal(weighted.positions.attachment_vectors, baseline.positions.attachment_vectors)
    assert not np.allclose(actual[ChannelKind.SEGMENT_ORIGINS].data_values,
                           expected[ChannelKind.SEGMENT_ORIGINS].data_values, equal_nan=True)
    selected = actual[ChannelKind.SEGMENT_ORIGINS].companion_values("entry_presence").all(axis=-1)
    assert np.isnan(actual[ChannelKind.SEGMENT_ORIGINS].data_values[~selected]).all()
    assert not selected[1, weighted.indices["left_clavicle"]]
    assert not selected[2].any()
    model = actual[ChannelKind.LANDMARKS_3D]
    center = weighted.center.calculate(positions=model.data_values[:, weighted._position_columns],
        landmark_present=model.companion_values("entry_presence").all(axis=-1)[:, weighted._position_columns])
    np.testing.assert_allclose(actual[ChannelKind.DERIVED_POINTS].data_values[:, 0],
        np.where(center.body_present[:, None], center.body_positions, np.nan))


def test_prepared_solver_survives_changing_scale_fit():
    bundle, fit, poses = pose_fixture()
    outputs = RecordingPoseOutputs(bundle=bundle, fit=fit, compute_center_of_mass=False)
    prepared_solver = outputs.weighted_attachments
    assert prepared_solver.strength == 1.
    before = calculate_channels(outputs, poses)[ChannelKind.LANDMARKS_3D].data_values.copy()
    larger_fit = replace(fit, fitted_scale=fit.fitted_scale * 2,
        segment_scales={name: scale * 2 for name, scale in fit.segment_scales.items()},
        segment_lengths={name: length * 2 for name, length in fit.segment_lengths.items()})
    outputs.configure_fit(fit=larger_fit, reference_fit=larger_fit, reference_kind="recording_fit")
    after = calculate_channels(outputs, poses)
    fresh = calculate_channels(RecordingPoseOutputs(bundle=bundle, fit=larger_fit,
        compute_center_of_mass=False), poses)
    assert outputs.weighted_attachments is prepared_solver
    for kind in after:
        np.testing.assert_allclose(after[kind].data_values, fresh[kind].data_values)
    assert not np.allclose(before, after[ChannelKind.LANDMARKS_3D].data_values, equal_nan=True)


def test_no_fit_leaves_model_positions_missing():
    bundle, _, poses = pose_fixture()
    outputs = RecordingPoseOutputs(bundle=bundle, fit=None, compute_center_of_mass=True)
    assert outputs.weighted_attachments.strength == 1.
    result = calculate_channels(outputs, poses)
    for kind in (ChannelKind.SEGMENT_ORIGINS, ChannelKind.LANDMARKS_3D):
        assert np.isnan(result[kind].data_values).all()
        assert not result[kind].companion_values("entry_presence").any()


def test_recorded_settings_identify_actual_placement_policy():
    from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
    from freemocap.core.recording.result_processing.provenance import stage_settings
    bundle, fit, _ = pose_fixture()
    outputs = RecordingPoseOutputs(bundle=bundle, fit=fit, compute_center_of_mass=False)
    settings = stage_settings(ProcessingStage.RECONSTRUCTION, {})
    assert settings["segment_placement"]["standard_human"] == {
        "method": "weighted_attachments", "strength": outputs.weighted_attachments.strength}
    assert settings["segment_placement"]["other_models"] == {"method": "rigid_attachments"}


def test_other_models_use_existing_rigid_placement():
    bundle, fit, poses = pose_fixture()
    other = RecordingPoseOutputs(bundle=replace(bundle, model_id="another_model"),
        fit=fit, compute_center_of_mass=False)
    assert other.weighted_attachments is None
    result = calculate_channels(other, poses)[ChannelKind.SEGMENT_ORIGINS]
    selected = result.companion_values("entry_presence").all(axis=-1)
    expected = other.positions.positions(world_orientations=poses.orientations,
        segment_present=selected, anchor_origins=poses.origins[:, other.positions.anchor_index])
    np.testing.assert_allclose(result.data_values, expected.segment_origins)
