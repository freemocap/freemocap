"""Check reference camera transport timing independently of inference speed."""
import json
import multiprocessing
from pathlib import Path
import numpy as np
import pytest
from freemocap.tests.reference_paths import prepared_root
from freemocap.tests.recording_datasets import synchronized_video_directory
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup


@pytest.mark.parametrize('dataset', ['freemocap_test_data', 'freemocap_sample_data'])
def test_camera_replay_preserves_recording_intervals(dataset):
    ready = prepared_root() / dataset / 'ready.json'
    if not ready.exists():
        pytest.skip(f'Prepare reference recording: {ready}')
    recording = Path(json.loads(ready.read_text())['recording'])
    group = MockCameraGroup.create(synchronized_videos_dir=synchronized_video_directory(recording),
        recording_folder=recording, global_kill_flag=multiprocessing.Value('b', False))
    try:
        for camera_id, timing in group.recording_timing.cameras.items():
            np.testing.assert_allclose(np.diff(group.capture_times_ns[camera_id]) / 1e9,
                np.diff(timing.timestamps_s), atol=2e-9, rtol=0)
        group.write_frame(0)
        group.write_frame(1)
        for camera_id in group.camera_ids:
            assert group._recarray_for(camera_id).frame_metadata.timestamps.pre_frame_grab_ns[0] == group.capture_times_ns[camera_id][1]
    finally:
        group.close()
