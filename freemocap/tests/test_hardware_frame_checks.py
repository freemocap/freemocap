import cv2
import numpy as np
import pytest

from freemocap.tools.hardware_validation.frame_checks import (
    brightness_response, decode_image_payload, image_metrics, orientation_response, timing_metrics,
)
from skellycam.core.types.frontend_payload_bytearray import ImagePayloadFrame, ImagePayloadRequest, encode_image_payload
from skellycam.core.camera.config.camera_config import CameraConfig
from freemocap.tools.hardware_validation.hardware_run import inspect_stream


def test_reports_actual_sixteen_fps_instead_of_nominal_thirty():
    metrics = timing_metrics(np.arange(160) / 16.0, np.arange(160))
    assert metrics['measured_fps'] == pytest.approx(16.0)
    assert not metrics['within_one_percent_of_requested_fps']
    assert metrics['median_interval_ms'] == pytest.approx(62.5)
    with pytest.raises(ValueError, match='increase'):
        timing_metrics(np.array([0., 0., 1.]), np.arange(3))


def test_transport_checks_pixels_identity_dimensions_and_truncation():
    frame = ImagePayloadFrame('camera-A', 2, 100, 10.0, np.full((48, 64, 3), 100, dtype=np.uint8), 64, 48)
    _, _, payload = encode_image_payload(ImagePayloadRequest((frame,), (cv2.IMWRITE_JPEG_QUALITY, 90)))
    decoded = decode_image_payload(bytes(payload))
    assert decoded[0].camera_id == 'camera-A'
    assert decoded[0].camera_index == 2
    assert decoded[0].frame_number == 100
    assert image_metrics(decoded[0].image_pixels)['mean_brightness'] == pytest.approx(100, abs=2)
    with pytest.raises(ValueError, match='Truncated'):
        decode_image_payload(bytes(payload)[:-5])
    with pytest.raises(ValueError, match='Trailing'):
        decode_image_payload(bytes(payload) + b'junk')


def test_brightness_and_orientation_require_observed_image_changes():
    assert brightness_response(np.full(10, 40), np.full(10, 70), 1)['outcome'] == 'pass'
    assert brightness_response(np.full(10, 40), np.full(10, 40), 1)['outcome'] == 'inconclusive'
    pixels = np.zeros((120, 160, 3), dtype=np.uint8)
    pixels[10:45, 15:60] = 210
    pixels[65:100, 100:140] = 100
    assert orientation_response(pixels, cv2.rotate(pixels, cv2.ROTATE_90_CLOCKWISE), 0)['outcome'] == 'pass'
    assert orientation_response(pixels, pixels, 0)['outcome'] == 'fail'


def test_repeated_transport_messages_do_not_inflate_capture_fps(tmp_path):
    samples = []
    for ordinal, frame_number in enumerate((1, 1, 2, 2, 3, 3)):
        frame = ImagePayloadFrame('A', 0, frame_number, float(frame_number * 1e9 / 30),
                                  np.full((48, 64, 3), 100, dtype=np.uint8), 32, 24)
        _, timestamp, payload = encode_image_payload(ImagePayloadRequest((frame,), ()))
        samples.append((ordinal / 60.0, {'image': bytes(payload), 'timestamp': timestamp, 'sequence': frame_number}))
    config = CameraConfig(camera_id='A', camera_index=0, resolution={'width': 64, 'height': 48}, rotation=-1).model_dump(mode='json')
    report = inspect_stream(samples, {'A': config}, tmp_path, 'python')
    assert report['delivery']['measured_fps'] == pytest.approx(60.0)
    assert report['source_frames_received']['measured_fps'] == pytest.approx(30.0)
    assert report['duplicate_source_frames'] == 3
    assert not report['continuity_passed']
    assert (tmp_path / 'frame-observations.npz').is_file()
