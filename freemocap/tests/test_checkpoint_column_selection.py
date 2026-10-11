"""Column masks must preserve whole channel identities, including null references."""
import itertools
import unittest
import pyarrow as pa
from freemocap.core.recording.parquet_storage.checkpoint_publication import channel_selection_mask


class CheckpointColumnSelectionTests(unittest.TestCase):
    def test_matches_scalar_membership_for_mixed_identities_and_null_references(self):
        names = ("sensor_group", "source", "reference_frame", "channel")
        rows = list(itertools.product(("group.a", "group.b"), ("body", "board"),
                                     (None, "world", "image"), ("raw", "filtered")))
        batch = pa.RecordBatch.from_pylist([dict(zip(names,row)) for row in rows])
        for keys in (set(), set(rows), set(rows[::3]), {rows[0]}, {("unknown","body",None,"raw")}):
            self.assertEqual(channel_selection_mask(batch=batch,channel_keys=keys).to_pylist(),
                             [row in keys for row in rows])
            self.assertEqual(channel_selection_mask(batch=batch.slice(0,0),channel_keys=keys).to_pylist(), [])
