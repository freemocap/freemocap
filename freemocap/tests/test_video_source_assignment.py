"""Source collisions must fail before opening processing readers."""

from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper


class VideoSourceAssignmentTests(TestCase):
    def test_colliding_source_ids_do_not_open_or_overwrite_readers(self) -> None:
        with patch("freemocap.core.pipeline.posthoc.video_group_helper.ParsedVideoFilename.from_path",
                   return_value=SimpleNamespace(camera_id="same-source", camera_index=0)):
            with patch("freemocap.core.pipeline.posthoc.video_group_helper.VideoHelper.from_video_path") as reader:
                with self.assertRaisesRegex(ValueError, "Ambiguous video source IDs"):
                    VideoGroupHelper.from_video_paths(video_paths=[Path("first.mp4"), Path("second.mp4")])
                reader.assert_not_called()

    def test_ambiguous_order_requires_explicit_assignment(self) -> None:
        with patch("freemocap.core.pipeline.posthoc.video_group_helper.ParsedVideoFilename.from_path",
                   side_effect=[SimpleNamespace(camera_id="a", camera_index=0), SimpleNamespace(camera_id="b", camera_index=0)]):
            with patch("freemocap.core.pipeline.posthoc.video_group_helper.VideoHelper.from_video_path") as reader:
                with self.assertRaisesRegex(ValueError, "Ambiguous video source ordering"):
                    VideoGroupHelper.from_video_paths(video_paths=[Path("first.mp4"), Path("second.mp4")])
                reader.assert_not_called()
