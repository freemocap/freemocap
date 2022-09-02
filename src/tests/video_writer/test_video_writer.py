import os
import shutil
import time
from pathlib import Path
from unittest import TestCase

import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import VideoRecorder


class VideoWriterTestCase(TestCase):
    def setUp(self):
        self.test_folder = Path().joinpath("madeupvideowritertestingfolder").resolve()

    def tearDown(self):
        if os.path.exists(self.test_folder):
            shutil.rmtree(self.test_folder)

    def test_write_on_video_writer(self):
        example_payload = FramePayload(
            image=np.random.randint(0, 4, (720, 1280, 3)),
            timestamp_in_seconds_from_record_start=time.time_ns(),
        )
        vw = VideoRecorder()
        vw.append_frame_payload_to_list(example_payload)

        assert vw.frame_count == 1
