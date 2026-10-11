"""Retry only Windows replacement failures with documented unchanged file names."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from freemocap.core.recording.parquet_storage import shared_file


@unittest.skipUnless(os.name == "nt", "Windows replacement contract")
class RecordingFileRetryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source=Path(self.directory.name)/"source"
        self.destination=Path(self.directory.name)/"destination"
        self.source.write_bytes(b"new");self.destination.write_bytes(b"old")

    def test_transient_failure_retries_same_paths(self):
        with patch.object(shared_file,"_replace_file",side_effect=[False,True]) as replace, \
             patch.object(shared_file.ctypes,"get_last_error",return_value=1175), \
             patch.object(shared_file.time,"sleep") as sleep:
            shared_file.replace_recording_file(source=self.source,destination=self.destination)
        self.assertEqual(replace.call_count,2)
        self.assertEqual(replace.call_args_list[0],replace.call_args_list[1])
        sleep.assert_called_once_with(.01)

    def test_persistent_and_state_changing_errors_fail_without_destroying_inputs(self):
        for error, attempts in ((1175,6),(1176,1),(1177,1),(5,1)):
            with self.subTest(error=error), \
                 patch.object(shared_file,"_replace_file",return_value=False) as replace, \
                 patch.object(shared_file.ctypes,"get_last_error",return_value=error), \
                 patch.object(shared_file.time,"sleep") as sleep:
                with self.assertRaises(OSError) as caught:
                    shared_file.replace_recording_file(source=self.source,destination=self.destination)
                self.assertEqual(caught.exception.winerror,error)
                self.assertEqual(replace.call_count,attempts)
                self.assertEqual(sleep.call_count,attempts-1)
                self.assertEqual(self.source.read_bytes(),b"new")
                self.assertEqual(self.destination.read_bytes(),b"old")

    def test_actual_repeated_replacement_preserves_latest_content(self):
        for index in range(30):
            expected=str(index).encode()
            self.source.write_bytes(expected)
            shared_file.replace_recording_file(source=self.source,destination=self.destination)
            self.assertFalse(self.source.exists())
            self.assertEqual(self.destination.read_bytes(),expected)
