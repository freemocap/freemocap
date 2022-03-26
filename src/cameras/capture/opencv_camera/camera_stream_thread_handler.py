import logging
import threading
import time
import traceback
from pathlib import Path
from uuid import uuid4

from src.cameras.capture.dataclasses.frame_payload import FramePayload
from src.cameras.persistence.video_writer.save_options import SaveOptions
from src.cameras.persistence.video_writer.video_writer import VideoWriter
from src.config.data_paths import freemocap_data_path

logger = logging.getLogger(__name__)


class CameraStreamThreadHandler(threading.Thread):
    def __init__(
        self,
        session_id: str,
        camera_name: str,
        get_next_frame,
        frame_width: int,
        frame_height: int,
        save_video=False,
    ):
        super().__init__()
        self._session_id = session_id
        self._camera_name = camera_name
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._save_video = save_video
        self._is_capturing_frames = False
        self._get_next_frame = get_next_frame
        self._num_frames_processed = 0
        self._elapsed = 0
        self._frame: FramePayload = FramePayload()
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
            freemocap_data_path, f"{self._session_id}"
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
                frame = self._get_next_frame()
                self._frame = frame
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
                path_to_save_video=self.session_writer_path / 'synchronized_videos',
                camera_name=self._camera_name,
                frames_per_second=self.current_fps,
                frame_width=self._frame_width,
                frame_height=self._frame_height,
            )
            video_writer.save(options)
