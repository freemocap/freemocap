"""Independent measurements from decoded pixels and recorded capture timestamps."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import av
import numpy as np
import polars as pl

from skellycam.core.types.frontend_payload_bytearray import (
    FRONTEND_FRAME_HEADER_DTYPE, FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE,
)
from skellycam.core.recorders.videos.recording_metadata import (
    RecordingFileField, read_recording_field, resolve_recording_file,
)
from skellycam.core.timestamps.recording_timing_reader import recorded_camera_timing_path
from skellycam.core.recorders.videos.video_associations import VideoAssociations
from skellycam.system.default_paths import SYNCHRONIZED_VIDEOS_FOLDER_NAME


@dataclass(frozen=True)
class DecodedImage:
    camera_id: str
    camera_index: int
    frame_number: int
    image_pixels: np.ndarray


def decode_image_payload(payload: bytes) -> list[DecodedImage]:
    offset = 0

    def read_header(dtype):
        nonlocal offset
        if offset + dtype.itemsize > len(payload):
            raise ValueError('Truncated image header')
        value = np.frombuffer(payload, dtype=dtype, count=1, offset=offset)[0]
        offset += dtype.itemsize
        return value

    opening = read_header(FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    if opening['message_type'] != 0 or opening['number_of_cameras'] < 1:
        raise ValueError('Invalid image group header')
    frames = []
    for _ in range(int(opening['number_of_cameras'])):
        header = read_header(FRONTEND_FRAME_HEADER_DTYPE)
        length = int(header['jpeg_string_length'])
        if header['message_type'] != 1 or header['frame_number'] != opening['frame_number']:
            raise ValueError('Image frame identity disagrees with group')
        if length < 1 or offset + length > len(payload):
            raise ValueError('Invalid JPEG byte length')
        pixels = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8, count=length, offset=offset), cv2.IMREAD_COLOR)
        offset += length
        expected_shape = (int(header['image_height']), int(header['image_width']), int(header['color_channels']))
        if pixels is None or pixels.shape != expected_shape:
            raise ValueError('Decoded image dimensions disagree with header')
        frames.append(DecodedImage(bytes(header['camera_id']).decode('ascii'), int(header['camera_index']),
                                   int(header['frame_number']), pixels))
    closing = read_header(FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE)
    if closing['message_type'] != 2 or closing['frame_number'] != opening['frame_number'] or closing['number_of_cameras'] != opening['number_of_cameras']:
        raise ValueError('Image group footer disagrees with header')
    if offset != len(payload) or len({frame.camera_id for frame in frames}) != len(frames) or len({frame.camera_index for frame in frames}) != len(frames):
        raise ValueError('Trailing image bytes or duplicate camera identities')
    return frames


def timing_metrics(timestamps_seconds: np.ndarray, frame_numbers: np.ndarray, expected_fps: float = 30.0) -> dict:
    timestamps = np.asarray(timestamps_seconds, dtype=np.float64)
    numbers = np.asarray(frame_numbers, dtype=np.int64)
    if timestamps.ndim != 1 or timestamps.size < 3 or numbers.shape != timestamps.shape or not np.isfinite(timestamps).all():
        raise ValueError('At least three finite capture timestamps with matching frame identities are required')
    intervals = np.diff(timestamps)
    if np.any(intervals <= 0) or np.any(np.diff(numbers) <= 0):
        bad = np.flatnonzero((intervals <= 0) | (np.diff(numbers) <= 0))[:5]
        detail = [(int(index), numbers[index:index + 2].tolist(), timestamps[index:index + 2].tolist()) for index in bad]
        raise ValueError(f'Capture timestamps and frame identities must increase: {detail}')
    fps = float((timestamps.size - 1) / (timestamps[-1] - timestamps[0]))
    jitter_ms = np.abs(intervals - 1.0 / expected_fps) * 1000.0
    return {'frame_count': int(numbers.size), 'measured_fps': fps,
            'median_interval_ms': float(np.median(intervals) * 1000),
            'p99_interval_ms': float(np.percentile(intervals, 99) * 1000),
            'maximum_interval_ms': float(intervals.max() * 1000),
            'p99_nominal_jitter_ms': float(np.percentile(jitter_ms, 99)),
            'missing_frame_numbers': int(np.maximum(np.diff(numbers) - 1, 0).sum()),
            'within_one_percent_of_requested_fps': abs(fps - expected_fps) <= expected_fps * 0.01}


def image_metrics(pixels: np.ndarray) -> dict:
    gray = cv2.cvtColor(pixels, cv2.COLOR_BGR2GRAY)
    return {'width': int(pixels.shape[1]), 'height': int(pixels.shape[0]),
            'mean_brightness': float(gray.mean()), 'brightness_std': float(gray.std()),
            'black_fraction': float(np.mean(gray <= 2)), 'white_fraction': float(np.mean(gray >= 253))}


def brightness_response(before_means: np.ndarray, after_means: np.ndarray, expected_direction: int) -> dict:
    before = np.asarray(before_means, dtype=np.float64)
    after = np.asarray(after_means, dtype=np.float64)
    if min(before.size, after.size) < 5 or expected_direction not in (-1, 1):
        raise ValueError('Brightness comparison needs five frames per setting and a signed expected direction')
    difference = float(np.median(after) - np.median(before))
    noise = float(max(np.percentile(before, 90) - np.percentile(before, 10), np.percentile(after, 90) - np.percentile(after, 10)))
    return {'median_brightness_change': difference, 'scene_variation': noise,
            'outcome': 'pass' if difference * expected_direction > max(3.0, noise) else 'inconclusive'}


def orientation_response(before_pixels: np.ndarray, after_pixels: np.ndarray, expected_rotation: int) -> dict:
    scores = {}
    for rotation in (-1, 0, 1, 2):
        rotated = before_pixels if rotation == -1 else cv2.rotate(before_pixels, rotation)
        reference = cv2.resize(cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY), (96, 96)).astype(np.float64).ravel()
        observed = cv2.resize(cv2.cvtColor(after_pixels, cv2.COLOR_BGR2GRAY), (96, 96)).astype(np.float64).ravel()
        scores[str(rotation)] = float(np.corrcoef(reference, observed)[0, 1]) if reference.std() > 1 and observed.std() > 1 else 0.0
    ordered = sorted(scores, key=scores.get, reverse=True)
    confident = scores[ordered[0]] > 0.8 and scores[ordered[0]] - scores[ordered[1]] > 0.1
    return {'correlations': scores, 'detected_rotation': int(ordered[0]),
            'outcome': ('pass' if int(ordered[0]) == expected_rotation else 'fail') if confident else 'inconclusive'}


def audit_recording(recording_directory: Path, expected_camera_ids: tuple[str, ...], expected_fps: float = 30.0) -> dict:
    videos = read_recording_field(recording_folder=recording_directory, field=RecordingFileField.VIDEOS)
    if not isinstance(videos, dict) or set(videos) != set(expected_camera_ids):
        raise ValueError('Recorded video identities disagree with requested cameras')
    result = {'cameras': {}}
    video_paths = VideoAssociations(videos).resolve_paths(video_folder=recording_directory / SYNCHRONIZED_VIDEOS_FOLDER_NAME)
    timestamp_arrays = []
    index_arrays = []
    for camera_id, relative_path in videos.items():
        timing_path = recorded_camera_timing_path(recording_folder=recording_directory, camera_id=camera_id)
        if timing_path is None:
            raise ValueError(f'Missing capture timestamps for {camera_id}; nominal video FPS is not a substitute')
        table = pl.read_csv(timing_path, infer_schema_length=0)
        table = table.rename({name: name.removeprefix('# ') for name in table.columns})
        numbers = table['recording_frame_number'].cast(pl.Int64).to_numpy()
        timestamps = table['timestamp.from_recording_start.sec'].cast(pl.Float64).to_numpy()
        metrics = timing_metrics(timestamps, numbers, expected_fps)
        decoded_count = 0
        dimensions = set()
        first_image = None
        with av.open(str(video_paths[camera_id])) as capture:
            for video_frame in capture.decode(video=0):
                pixels = video_frame.to_ndarray(format='bgr24')
                decoded_count += 1
                dimensions.add(pixels.shape)
                if first_image is None:
                    first_image = image_metrics(pixels)
        metrics.update(decoded_frames=decoded_count, decoded_shapes=sorted(dimensions), first_image=first_image)
        metrics['video_matches_capture_timestamps'] = decoded_count == len(numbers) and len(dimensions) == 1
        result['cameras'][camera_id] = metrics
        timestamp_arrays.append(timestamps)
        index_arrays.append(numbers)
    result['matching_camera_frame_indices'] = all(np.array_equal(index_arrays[0], indices) for indices in index_arrays)
    if result['matching_camera_frame_indices']:
        spreads_ms = np.ptp(np.stack(timestamp_arrays), axis=0) * 1000
        result['host_timestamp_spread_ms'] = {'median': float(np.median(spreads_ms)), 'p99': float(np.percentile(spreads_ms, 99)), 'maximum': float(spreads_ms.max())}
        result['timestamp_interpretation'] = ('Host timestamp spread is not sensor exposure synchronization. '
            'Python DirectShow grab-call timestamps and Rust frame-available timestamps describe different events.')
    result['passed'] = result['matching_camera_frame_indices'] and all(
        camera['video_matches_capture_timestamps'] and camera['missing_frame_numbers'] == 0
        and camera['within_one_percent_of_requested_fps'] for camera in result['cameras'].values())
    return result
