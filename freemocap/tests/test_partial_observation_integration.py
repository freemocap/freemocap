"""Core preserves Forge provenance and temporal boundaries on the recording grid."""
from types import SimpleNamespace

import numpy as np
import pytest

from freemocap.core.recording.result_processing import skeleton_fitting as stage
from freemocap.core.reconstruction.trajectory_gap_filling import fill_trajectory_gaps, GapFillingReport
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points, PosthocFilterConfig
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle


def test_core_delegates_gap_filling_and_serializes_absence_provenance():
    from skellyforge.core.trajectories import fill_trajectory_gaps as forge_fill
    points = np.ones((30, 2, 3)); points[5:8, 0] = np.nan; points[12:17] = np.nan
    times = np.arange(30) / 10
    expected, forge_report = forge_fill(points=points, timestamps_s=times)
    result = prepare_recording_points(points=points, timestamps_s=times, config=PosthocFilterConfig(enabled=False))
    np.testing.assert_array_equal(result.points, expected)
    report = GapFillingReport.model_validate_json(result.report.gap_filling.model_dump_json())
    assert report.model_dump() == forge_report.to_dict()
    assert report.active_spans == ((0, 12), (17, 30))
    assert np.isnan(result.points[12:17]).all()
    assert not report.measured_support(result.points)[5:8, 0].any()


@pytest.mark.parametrize('second_root', [False, True])
def test_fitting_never_borrows_root_or_temporal_history_across_absence(monkeypatch, second_root):
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    model = RecordedModel.from_bundle(bundle)
    root = bundle.rest_pose.root_segment_name
    records = [dict(number=i * 2, time=i / 10, keypoints={'p': np.ones(3)}, points={},
                    origins={root: np.zeros(3)}, rotations={root: np.array([1., 0., 0., 0.])}) for i in range(14)]
    for i in (4, 9, 12, 13): records[i] = dict(records[i], keypoints={}, origins={}, rotations={})
    # The second appearance has no root seed. It must not borrow the first one's.
    if not second_root:
        for i in range(5, 9): records[i]['origins'] = records[i]['rotations'] = {}
    inputs = stage.SavedSkeletonFitInputs(records, model,
        RecordingScaleFit.model_construct(fit=SimpleNamespace(segment_scales={})), 'world', 'signature')
    calls = []
    def solve(skeleton, saved_model, scales, selected, *, progress):
        calls.append([r['number'] for r in selected])
        n = len(selected)
        windows = [dict(index=i, fixed_start=max(0,i-2), active_start=i, active_end=i+2) for i in range(n-2)]
        for window in windows: progress(window, len(windows))
        result = SimpleNamespace(quaternions=np.tile([1.,0.,0.,0.],(n,1,1)),
            translations=np.zeros((n,1,3)), linkage_displacements=np.zeros((n,1,3)),
            lengths=np.ones((n,1)), processing={'windows':windows}, converged=True)
        return stage.RecordingHumanFit(dict(names=[root], references=[1.], display_names=[['root']]),
                                       result, {'root':np.zeros((n,3))})
    monkeypatch.setattr(stage, 'fit_human', solve)
    updates = []
    result = stage.fit_visible_intervals(inputs, progress=lambda window, total: updates.append((window, total)))
    assert calls == ([[0, 2, 4, 6], [10, 12, 14, 16]] if second_root else [[0, 2, 4, 6]])
    skipped = [] if second_root else [dict(start=5, stop=9, reason='no_root_pose_in_interval')]
    assert result.sequence.processing['skipped_intervals'] == [*skipped,
        dict(start=10, stop=12, reason='fewer_than_three_frames')]
    assert [window['index'] for window, _ in updates] == list(range(4 if second_root else 2))
    assert all(total == len(updates) for _, total in updates)
    if second_root: assert updates[2][0]['active_start'] == 5
    channels = stage.fitted_channels(fit=result, sensor_group='cameras', source='fit', reference_frame='world')
    for channel in channels:
        assert channel.values.shape[0] == len(records)
        assert np.isfinite(channel.values[:4]).all()
        assert np.isnan(channel.values[[4, 9, 10, 11, 12, 13]]).all()
        assert (np.isfinite(channel.values[5:9]).all() if second_root else np.isnan(channel.values[5:9]).all())
    assert records[4]['number'] == 8  # Original frame grid is never compacted.


def test_all_blank_interval_retains_null_model_channels_without_solving(monkeypatch):
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    model = RecordedModel.from_bundle(bundle)
    records = [dict(number=i, time=i / 10, points={}, keypoints={}, origins={}, rotations={}) for i in range(3)]
    scale = RecordingScaleFit.model_construct(fit=SimpleNamespace(
        segment_scales=dict.fromkeys(bundle.skeleton.segments, 1700.)))
    def unexpected(*args, **kwargs):
        raise AssertionError('No solver call is valid without evidence')
    monkeypatch.setattr(stage, 'fit_human', unexpected)
    result = stage.fit_visible_intervals(stage.SavedSkeletonFitInputs(records, model, scale, 'world', 'signature'))
    channels = stage.fitted_channels(fit=result, sensor_group='cameras', source='fit', reference_frame='world')
    assert set(result.landmarks) == set(bundle.skeleton.landmarks)
    assert all(np.isnan(channel.values).all() for channel in channels)
    assert result.sequence.processing['fitted_frames'] == [False, False, False]
