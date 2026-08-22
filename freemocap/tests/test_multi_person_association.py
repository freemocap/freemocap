import numpy as np

from freemocap.core.tracking.multi_person_association import (
    CrossCameraAssociator,
    PersonDescriptor,
    appearance_histogram,
    associate_two_person_views,
    bone_length_signature,
    performer_parquet_rows,
)
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig


def _descriptor(
    identifier: str, x: float, signature: list[float], colour_bin: int
) -> PersonDescriptor:
    histogram = np.zeros(512)
    histogram[colour_bin] = 1.0
    return PersonDescriptor(
        detection_id=identifier,
        pelvis=np.array([x, 0.0, 0.0]),
        bone_signature=np.asarray(signature),
        appearance_histogram=histogram,
    )


def test_cross_camera_order_change_preserves_two_identities():
    references = [
        _descriptor("performer-1", -100.0, [0.8, 1.2], 4),
        _descriptor("performer-2", 100.0, [1.3, 0.7], 400),
    ]
    candidates = [
        _descriptor("camera-b-track-9", 110.0, [1.3, 0.7], 400),
        _descriptor("camera-b-track-2", -90.0, [0.8, 1.2], 4),
    ]
    assert associate_two_person_views(references, candidates) == {
        "performer-1": "camera-b-track-2",
        "performer-2": "camera-b-track-9",
    }


def test_ambiguous_identity_is_held_instead_of_swapped():
    identical = [1.0, 1.0]
    references = [_descriptor("performer-1", 0, identical, 10)]
    candidates = [
        _descriptor("candidate-a", -1, identical, 10),
        _descriptor("candidate-b", 1, identical, 10),
    ]
    assert associate_two_person_views(references, candidates) == {}


def test_features_and_parquet_rows_include_performer_id():
    image = np.full((4, 4, 3), [255, 0, 0], dtype=np.uint8)
    assert appearance_histogram(image, (0, 0, 4, 4)).sum() == 1.0
    points = {
        "left_hip": np.array([-1.0, 0.0, 0.0]),
        "right_hip": np.array([1.0, 0.0, 0.0]),
    }
    assert np.isfinite(bone_length_signature(points)).all()
    rows = performer_parquet_rows(4, {"performer-1": points})
    assert {row["performer_id"] for row in rows} == {"performer-1"}


def test_cross_camera_associator_preserves_primary_ids_when_detector_order_flips():
    zero_hist = np.zeros(512, dtype=np.float64)

    def descriptor(identity: str, signature: float) -> PersonDescriptor:
        return PersonDescriptor(identity, np.zeros(3), np.array([signature]), zero_hist)

    associator = CrossCameraAssociator()
    first = associator.assign(
        {
            "cam-a": [descriptor("track-a", 0.1), descriptor("track-b", 0.9)],
            "cam-b": [descriptor("other-b", 0.9), descriptor("other-a", 0.1)],
        }
    )
    assert first == {
        "performer-1": {"cam-a": "track-a", "cam-b": "other-a"},
        "performer-2": {"cam-a": "track-b", "cam-b": "other-b"},
    }
    second = associator.assign(
        {
            "cam-a": [descriptor("track-b", 0.9), descriptor("track-a", 0.1)],
            "cam-b": [descriptor("other-a", 0.1), descriptor("other-b", 0.9)],
        }
    )
    assert second["performer-1"]["cam-a"] == "track-a"
    assert second["performer-2"]["cam-a"] == "track-b"


def test_multi_person_config_uses_the_selected_lightweight_model():
    config = CameraNodeConfig(
        multi_person_enabled=True,
        rtmpose_model_name="rtmw-l-m_256x192",
        rtmpose_confidence_threshold=0.01,
    )
    detector = config.skeleton_tracker_config.stages[0].keypoint_detectors[0]
    assert detector.model_name == "rtmw-l-m_256x192"
    assert detector.confidence_threshold == 0.01
