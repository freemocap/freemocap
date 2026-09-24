"""A reconstruction refresh preserves saved evidence and fails before replacement."""

import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_reconstruction
from freemocap.tests.test_saved_reconstruction import saved_request  # noqa: F401
from freemocap.tests import refresh_recording_reconstruction as refresh


def test_refresh_preserves_inputs_and_is_repeatable(saved_request):
    path = saved_request.structure.data_parquet_path
    before = pq.read_table(path).replace_schema_metadata(None)
    bundle = read_saved_reconstruction(saved_request).numerical_input.bundles[0]
    for _ in range(2):
        report = refresh.refresh_reconstruction(saved_request.structure, bundle)
        assert report["frames"] == 2
        table = pq.read_table(path).replace_schema_metadata(None)
        inputs = table.filter(pc.equal(table['source'], saved_request.point_source))
        assert inputs.equals(before)
        loaded = read_saved_reconstruction(saved_request)
        assert loaded.points.frames == (10, 11)
        assert loaded.points.timestamps_s == (1.0, 1.07)
        assert set(read_metadata(path=path).runs) == {3}


def test_refresh_failure_leaves_recording_unchanged(saved_request, monkeypatch):
    path = saved_request.structure.data_parquet_path
    before = path.read_bytes()
    bundle = read_saved_reconstruction(saved_request).numerical_input.bundles[0]

    def fail(_):
        raise RuntimeError("reconstruction failed")

    monkeypatch.setattr(refresh, 'reconstruct_skeletons_for_recording', fail)
    with pytest.raises(RuntimeError, match='reconstruction failed'):
        refresh.refresh_reconstruction(saved_request.structure, bundle)
    assert path.read_bytes() == before
