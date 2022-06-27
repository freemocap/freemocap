import os
import shutil
import time
from pathlib import Path
from unittest import TestCase

import numpy as np

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.video_recorder import SaveOptions, VideoRecorder


class VideoWriterTestCase(TestCase):
    def setUp(self):
        self.test_folder = Path().joinpath("madeupvideowritertestingfolder").resolve()

    def tearDown(self):
        if os.path.exists(self.test_folder):
            shutil.rmtree(self.test_folder)

    def test_write_on_video_writer(self):
        example_payload = FramePayload(
            image=np.random.randint(0, 4, (720, 1280, 3)), timestamp=time.time_ns()
        )
        vw = VideoRecorder()
        vw.append_frame_payload_to_list(example_payload)

        assert vw.frame_count == 1

    def test_save_creates_video_file(self):
        file_path = self.test_folder
        example_payload = FramePayload(
            image=np.random.randint(0, 4, (720, 1280, 3)), timestamp=time.time_ns()
        )
        vw = VideoRecorder()
        vw.append_frame_payload_to_list(example_payload)

        save_options = SaveOptions(
            writer_dir=file_path,
            filename="movie.mp4",
            frame_width=1280,
            frame_height=720,
            fps=1,
        )

        vw.save_list_of_frames_to_video_file(save_options)
        expected_path = Path().joinpath(file_path, "movie.mp4")

        assert save_options.full_path == expected_path, "Paths do not match"
        assert os.path.exists(expected_path), "File does not exist"
