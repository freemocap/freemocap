"""Independent recording resources survive failures in sibling resources."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from freemocap.api.http.playback.playback_router import get_recording_bundle
from freemocap.api.http.playback.resource_loading import RecordingResource


class BundleResourceTests(unittest.TestCase):
    def test_invalid_outputs_do_not_hide_raw_or_annotated_videos(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            recording = Path(temporary) / "recording"
            for folder, filename in (("synchronized_videos", "camera.avi"), ("annotated_videos", "camera_annotated.avi")):
                path = recording / folder / filename
                path.parent.mkdir(parents=True)
                writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (64, 48))
                self.assertTrue(writer.isOpened())
                try:
                    for _ in range(3):
                        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
                finally:
                    writer.release()
            (recording / "recording_data.parquet").write_bytes(b"invalid parquet")
            (recording / "tracker_schema.json").write_text("invalid json", encoding="utf-8")
            bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertIsNone(bundle.manifest)
            self.assertIsNone(bundle.tracker_schema)
            self.assertEqual(len(bundle.media), 2)
            self.assertTrue(all(source.valid for source in bundle.videos.sources.values()))
            self.assertEqual(bundle.media[0].timeline, bundle.media[1].timeline)
            self.assertTrue({RecordingResource.RECONSTRUCTION, RecordingResource.TRACKER_SCHEMA}.issubset(
                {error.resource for error in bundle.errors}))
            metadata_path = recording / "recording_info.json"
            metadata_path.write_text("invalid json", encoding="utf-8")
            bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertEqual(len(bundle.media), 2)
            self.assertIn(RecordingResource.MEDIA_ASSOCIATIONS, {error.resource for error in bundle.errors})
            metadata_path.write_text(json.dumps({"videos": {"declared-source": "camera.avi"}}), encoding="utf-8")
            bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertEqual({item.timeline.source for item in bundle.media}, {"declared-source"})
            with patch("freemocap.api.http.playback.playback_router.compute_recording_status", side_effect=ValueError("bad status")):
                bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertIsNone(bundle.status_summary)
            self.assertEqual(len(bundle.media), 2)
            (recording / "synchronized_videos" / "camera.avi").write_bytes(b"broken video")
            bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertEqual(bundle.videos.preferred_source, "annotated")
            self.assertEqual(len(bundle.media), 1)
            self.assertTrue(bundle.videos.sources["annotated"].valid)
            self.assertIn(RecordingResource.RAW_VIDEO, {error.resource for error in bundle.errors})

    def test_recording_without_videos_returns_its_resource_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            recording = Path(temporary) / "recording"
            recording.mkdir()
            (recording / "recording_data.parquet").write_bytes(b"invalid parquet")
            bundle = get_recording_bundle(recording_id="recording", recording_parent_directory=temporary)
            self.assertEqual(bundle.media, ())
            self.assertFalse(any(source.available for source in bundle.videos.sources.values()))
            self.assertIn(RecordingResource.RECONSTRUCTION, {error.resource for error in bundle.errors})
