import logging
import threading
import time
import traceback
from pathlib import Path
from uuid import uuid4

from src.cameras.dto import FramePayload
from src.cameras.dtos.create_writer_options import get_canonical_time_str
from src.cameras.video_writer.video_writer import SaveOptions, VideoWriter
from src.config.data_paths import freemocap_data_path

logger = logging.getLogger(__name__)


class FrameThread(threading.Thread):
    def __init__(
        self,
        webcam_id: str,
        get_next_frame,
        frame_width: int,
        frame_height: int,
        save_video=False,
    ):
        super().__init__()
        self._webcam_id = webcam_id
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._save_video = save_video
        self._is_capturing_frames = False
        self._get_next_frame = get_next_frame
        self._num_frames_processed = 0
        self._elapsed = 0
        self._frame: FramePayload = FramePayload()
        self._session_id = uuid4()
        self._session_timestr = get_canonical_time_str()
        self.setDaemon(True)

    @property
    def current_fps(self):
        if self._elapsed <= 0:
            return 0
        if self._num_frames_processed <= 0:
            return 0
        return self._num_frames_processed / self._elapsed

    @property
    def session_writer_path(self):
        return Path().joinpath(
            freemocap_data_path, f"{self._session_timestr}_{self._session_id}"
        )

    @property
    def latest_frame(self):
        return self._frame

    @property
    def is_capturing_frames(self):
        return self._is_capturing_frames

    def stop(self):
        self._is_capturing_frames = False

    def run(self):
        self._start_frame_loop(self._save_video)

    def _start_frame_loop(self, save_video=False):
        video_writer = VideoWriter()
        self._is_capturing_frames = True
        start = time.time()
        try:
            while self._is_capturing_frames:
                success, image, timestamp = self._get_next_frame()
                self._frame = FramePayload(success, image, timestamp)
                if save_video:
                    video_writer.write(self._frame)
                self._num_frames_processed += 1
                self._elapsed = time.time() - start
        except:
            logger.error("Frame loop thread exited due to error")
            traceback.print_exc()
        else:
            logger.info("Frame loop thread exited.")
        finally:
            options = SaveOptions(
                writer_dir=Path().joinpath(
                    self.session_writer_path,
                    "raw_frame_capture",
                    f"webcam_{self._webcam_id}",
                ),
                fps=self.current_fps,
                frame_width=self._frame_width,
                frame_height=self._frame_height,
            )
            video_writer.save(options)
