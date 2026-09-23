"""Real reference consumers share one validated preparation per session."""

from pathlib import Path

import pytest

from freemocap.tests.prepare_recording_dataset import file_digest, prepare
from freemocap.tests.recording_datasets import TEST_DATA
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture(scope="session")
def prepared_reference():
    base = Path.home() / "freemocap_data"
    recording = prepare(TEST_DATA, recordings_root=base / "recordings",
                        prepared_root=base / "testing" / "prepared", fresh=False, timeout=1800.0)
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    paths = [structure.data_parquet_path, *recording.glob("*calibration*.toml")]
    before = {path: file_digest(path) for path in paths}
    yield structure
    assert {path: file_digest(path) for path in paths} == before, "Consumer tests changed prepared results"
