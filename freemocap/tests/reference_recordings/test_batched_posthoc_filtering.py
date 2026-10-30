"""Use full-rate sample_data to verify filtering; 6-fps test_data is unsuitable."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from freemocap.core.reconstruction import posthoc_filtering as filtering
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.reference_paths import prepared_root
from freemocap.tests.test_batched_posthoc_filtering import scalar_filter_reference
from freemocap.tools.datasets.catalog import SAMPLE_DATA
from freemocap.tools.datasets.preparation import file_digest


def sample_filter_inputs():
    root = prepared_root() / SAMPLE_DATA.name
    ready = root / 'ready.json'
    if not ready.exists():
        pytest.skip('Prepare full-rate sample_data under FREEMOCAP_PROVENANCE_PREPARED_ROOT')
    recording = Path(json.loads(ready.read_text(encoding='utf-8'))['recording'])
    if not recording.resolve().is_relative_to((root / 'current').resolve()):
        raise ValueError('Reference recording escapes the selected prepared root')
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    with recording_view(structure.data_parquet_path) as view:
        run_id = view.metadata.selected_run_id
        channels = [channel for channel in view.metadata.runs[run_id].channels if channel.kind == 'RAW_KEYPOINTS_3D']
        assert channels
        values = [read_saved_channel(structure=structure, run_id=run_id, metadata=view.metadata, channel=channel, view=view)
                  for channel in channels]
    return structure, values


@pytest.mark.skipif(not os.environ.get('FREEMOCAP_PROVENANCE_PREPARED_ROOT'), reason='Set the prepared reference-data root')
def test_full_rate_sample_filter_matches_scalar_calculation_without_changing_source():
    structure, channels = sample_filter_inputs()
    digest = file_digest(structure.data_parquet_path)
    config = filtering.PosthocFilterConfig()
    for channel in channels:
        points = channel.values
        times = np.asarray(channel.timestamps_s)
        assert len(times) == SAMPLE_DATA.expected_frame_count
        assert filtering.validate_filter_timing(timestamps_s=times, config=config) > config.cutoff * 2
        expected, filtered, short = scalar_filter_reference(points, times, config)
        with patch.object(filtering, 'sosfiltfilt', wraps=filtering.sosfiltfilt) as execute:
            actual = filtering.filter_recording_points(points=points, timestamps_s=times, config=config)
        np.testing.assert_allclose(actual.points, expected, rtol=0, atol=1e-10)
        np.testing.assert_array_equal(np.isnan(actual.points), np.isnan(points))
        assert actual.report.filtered_runs == filtered
        assert actual.report.preserved_short_runs == short
        assert execute.call_count < filtered
    assert file_digest(structure.data_parquet_path) == digest
