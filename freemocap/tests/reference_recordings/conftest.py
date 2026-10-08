"""Real reference consumers share one validated preparation per session."""

import pytest

from freemocap.tests.prepare_recording_dataset import file_digest, prepare
from freemocap.tests.recording_datasets import TEST_DATA
from freemocap.tests.reference_paths import prepared_root, recordings_root
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture(scope="session")
def prepared_reference():
    recording = prepare(TEST_DATA, recordings_root=recordings_root(),
                        prepared_root=prepared_root(), fresh=False, timeout=1800.0)
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    paths = [structure.data_parquet_path, *recording.glob("*calibration*.toml")]
    before = {path: file_digest(path) for path in paths}
    yield structure
    assert {path: file_digest(path) for path in paths} == before, "Consumer tests changed prepared results"
