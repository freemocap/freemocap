import logging
import os
import shutil
import time
from os import listdir
from pathlib import Path
from unittest import TestCase

import numpy as np

from src.cameras.dto import FramePayload
from src.cameras.video_writer.video_writer import SaveOptions, VideoWriter


class VideoWriterTestCase(TestCase):
    def setUp(self):
        self.test_folder = Path().joinpath("madeupvideowritertestingfolder").resolve()

    def tearDown(self):
        if os.path.exists(self.test_folder):
            shutil.rmtree(self.test_folder)

    def test_write_on_video_writer(self):
        example_payload = FramePayload(
            image=np.random.randint(720, 1280, 3), timestamp=time.time_ns()
        )
        vw = VideoWriter()
        vw.write(example_payload)

        assert vw.frame_count == 1

    def test_save_creates_video_file(self):
        file_path = self.test_folder
        example_payload = FramePayload(
            image=np.random.randint(0, 4, (720, 1280, 3)), timestamp=time.time_ns()
        )
        logging.info(example_payload.image.shape)
        vw = VideoWriter()
        vw.write(example_payload)

        save_options = SaveOptions(
            writer_dir=file_path,
            filename="movie.mp4",
            frame_width=1280,
            frame_height=720,
            fps=1,
        )

        vw.save(save_options)
        logging.info(listdir(file_path))
        full_path = Path().joinpath(file_path, "movie.mp4")
        logging.info(full_path)

        assert save_options.full_path == full_path, "Paths do not match"
        assert os.path.exists(full_path), "File does not exist"
