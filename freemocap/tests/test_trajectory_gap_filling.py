import numpy as np

from freemocap.core.reconstruction.trajectory_gap_filling import fill_trajectory_gaps, GapFillingReport
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points, filter_recording_points, PosthocFilterConfig


def test_timestamp_interpolation_discards_singletons_and_records_provenance():
    times=np.array([0., .02, .04, .08, .12, .5, .8])
    points=np.full((7,3,3),np.nan)
    points[1,0]=[2,4,6];points[2,0]=[4,8,12];points[4,0]=[12,24,36]
    points[6,0]=[999,999,999]  # Isolated detection must not anchor the endpoint.
    points[3,1]=[9,8,7]
    before=points.copy()
    filled,report=fill_trajectory_gaps(points=points,timestamps_s=times)
    np.testing.assert_allclose(filled[:,0],[[2,4,6],[2,4,6],[4,8,12],[8,16,24],[12,24,36],[12,24,36],[12,24,36]])
    assert np.isnan(filled[:,1:]).all()
    assert report.unsupported_keypoint_indices==(1,2)
    decoded=GapFillingReport.model_validate_json(report.model_dump_json())
    np.testing.assert_array_equal(decoded.original_support(filled),np.isfinite(before).all(axis=-1))
    support=decoded.measured_support(filled)
    assert support[:,0].tolist()==[False,True,True,False,True,False,False]
    assert not support[:,1:].any()
    np.testing.assert_array_equal(points,before)


def test_short_gaps_bridge_but_short_trajectories_do_not_survive():
    times=np.arange(41)/100
    points=np.full((41,2,3),np.nan)
    points[[0,10,20],0]=1.  # Two 100 ms bridges create a supported 200 ms trajectory.
    points[:10,1]=2.  # Only 90 ms of support.
    filled,report=fill_trajectory_gaps(points=points,timestamps_s=times)
    assert np.isfinite(filled[:,0]).all()
    assert np.isnan(filled[:,1]).all()
    assert report.unsupported_keypoint_indices==(1,)


def test_contiguous_support_at_different_frame_rates():
    for rate in (6,30,60,120):
        times=np.arange(rate+1)/rate
        points=np.ones((len(times),1,3))
        filled,report=fill_trajectory_gaps(points=points,timestamps_s=times)
        np.testing.assert_array_equal(filled,points)
        assert not report.discarded_spans


def test_gap_fill_precedes_filtering_and_runs_when_smoothing_disabled():
    times=np.arange(100)/30
    points=np.repeat(np.sin(times*3)[:,None,None],3,axis=2)
    points[35:45]=np.nan
    completed,_=fill_trajectory_gaps(points=points,timestamps_s=times)
    config=PosthocFilterConfig(cutoff=5)
    actual=prepare_recording_points(points=points,timestamps_s=times,config=config)
    expected=filter_recording_points(points=completed,timestamps_s=times,config=config)
    np.testing.assert_array_equal(actual.points,expected.points)
    assert actual.report.filtered_runs==1
    disabled=prepare_recording_points(points=points,timestamps_s=times,config=PosthocFilterConfig(enabled=False))
    np.testing.assert_array_equal(disabled.points,completed)


def test_alignment_receives_only_measured_support(monkeypatch):
    from dataclasses import replace
    from freemocap.tests.test_mocap_alignment import alignment_request
    from freemocap.core.reconstruction.mocap_alignment import align_mocap_recording, AlignmentEvidence
    request=alignment_request()
    raw=request.triangulation.reconstruction.points_3d.copy();raw[0]=np.nan
    request=replace(request,triangulation=replace(request.triangulation,
        reconstruction=replace(request.triangulation.reconstruction,points_3d=raw)))
    collect=AlignmentEvidence.collect
    def check(*,request):
        assert np.isnan(request.positions[0]).all()
        assert (request.quality[0]==0).all()
        return collect(request=request)
    monkeypatch.setattr(AlignmentEvidence,'collect',check)
    result=align_mocap_recording(request=request)
    assert np.isfinite(result.filtered_points[0]).all()
    assert np.isnan(result.triangulation.reconstruction.points_3d[0]).all()


def test_completed_samples_do_not_vote_in_person_scale():
    from freemocap.tests.test_model_scale_in_the_loop import _standing_keypoints
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.core.reconstruction.recording_reconstruction import RecordingReconstructionInput
    from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording
    from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
    points = _standing_keypoints()
    frame = np.stack(list(points.values()))
    completed = np.repeat(frame[None], 7, axis=0)
    completed[1:6] *= 5
    support = np.ones(completed.shape[:2], dtype=bool)
    support[1:6] = False
    bundle = build_standard_human_bundle(detector_type='rtmpose')
    def fit(values, measured_support=None):
        return reconstruct_skeletons_for_recording(RecordingReconstructionInput(
            bundles=(bundle,), keypoint_names=tuple(points), keypoints_3d=values,
            measured_support=measured_support, compute_center_of_mass=False,
            timing=PosthocTimingReport(),
        ))[bundle.model_id]
    baseline = fit(np.stack([frame, frame]))
    result = fit(completed, support)
    assert result.scale_fit is not None and baseline.scale_fit is not None
    assert result.scale_fit.fitted_scale == baseline.scale_fit.fitted_scale
    assert all(frame is not None for frame in result.frames)
