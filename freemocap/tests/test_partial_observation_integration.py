"""Core preserves Forge trajectory provenance and absence boundaries."""
import numpy as np
from freemocap.core.reconstruction.trajectory_gap_filling import GapFillingReport
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points, PosthocFilterConfig


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
