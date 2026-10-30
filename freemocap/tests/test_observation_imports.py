"""Live observation storage must not initialize the saved-recording reader stack."""

import subprocess
import sys


def test_observation_import_does_not_load_parquet_readers():
    result = subprocess.run([sys.executable, '-I', '-B', '-c', '''
import sys
from freemocap.core.tracking.observation_series import RecordingObservationSeries
assert 'freemocap.core.recording.parquet_storage.recording_view' not in sys.modules
assert 'freemocap.core.recording.parquet_storage.selected_batches' not in sys.modules
from freemocap.core.recording.parquet_storage.saved_channel_arrays import ChannelArrays
from freemocap.core.recording.parquet_storage.channel_arrays import ChannelArrays as ReaderChannelArrays
assert ChannelArrays is ReaderChannelArrays
'''], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
