"""Center-of-mass tests on the single canonical body model.

Covers both entry points: from raw RTMPose tracker keypoints
(``calculate_center_of_mass_per_frame``) and from already-canonical positions
(``calculate_center_of_mass_from_canonical`` — the path used by the rigidified
skeleton, matching the posthoc ``rigid_xyz -> CoM`` flow).
"""
import numpy as np

from freemocap.core.tasks.mocap.center_of_mass import (
    CoMConfidence,
    calculate_center_of_mass_from_canonical,
    calculate_center_of_mass_per_frame,
    load_body_biomechanics,
)


def _upright_rtmpose_pose() -> dict[str, np.ndarray]:
    """A crude upright standing pose in mm (RTMPose body keypoint names)."""
    def p(x, y, z):
        return np.array([float(x), float(y), float(z)])
    return {
        "left_ear": p(-60, 1700, 0), "right_ear": p(60, 1700, 0),
        "left_shoulder": p(-200, 1450, 0), "right_shoulder": p(200, 1450, 0),
        "left_elbow": p(-220, 1150, 0), "right_elbow": p(220, 1150, 0),
        "left_wrist": p(-230, 900, 0), "right_wrist": p(230, 900, 0),
        "left_hip": p(-120, 950, 0), "right_hip": p(120, 950, 0),
        "left_knee": p(-130, 500, 0), "right_knee": p(130, 500, 0),
        "left_ankle": p(-140, 80, 0), "right_ankle": p(140, 80, 0),
        "left_big_toe": p(-140, 20, 150), "right_big_toe": p(140, 20, 150),
    }


def test_center_of_mass_uses_canonical_model():
    bio = load_body_biomechanics()
    assert bio.segment_connections is not None
    assert bio.center_of_mass_definitions is not None
    assert bio.tracker_mapping is not None

    result = calculate_center_of_mass_per_frame(_upright_rtmpose_pose(), bio)
    com = result.total_body_com
    assert com.shape == (3,)
    assert np.all(np.isfinite(com))
    assert 80.0 < com[1] < 1700.0
    assert result.confidence >= CoMConfidence.medium


def test_com_from_canonical_matches_tracker_path():
    # The refactor must be behaviour-preserving: feeding canonical positions
    # directly equals mapping tracker keypoints then computing CoM.
    bio = load_body_biomechanics()
    pose = _upright_rtmpose_pose()

    via_tracker = calculate_center_of_mass_per_frame(pose, bio)
    canonical = bio.tracker_mapping.apply(pose)
    via_canonical = calculate_center_of_mass_from_canonical(canonical, bio)

    assert np.allclose(via_tracker.total_body_com, via_canonical.total_body_com)
    assert via_canonical.confidence == via_tracker.confidence
