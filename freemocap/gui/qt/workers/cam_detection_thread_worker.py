import logging
import time
from typing import Any, Dict, List, Optional

import cv2
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class CamDetectionThreadWorker(QThread):
    in_progress = Signal(str)
    finished = Signal(list)

    def __init__(self, max_camera_index: int = 20, parent=None):
        super().__init__(parent)
        self._max_camera_index = max_camera_index
        self._warmup_frames = 5
        self._probe_timeout_seconds = 4.0
        self._frame_retry_sleep_seconds = 0.05
        self._slow_start_threshold_seconds = 1.0

    def run(self) -> None:
        detected_cameras: List[Dict[str, Any]] = []

        for camera_index in range(self._max_camera_index):
            self.in_progress.emit(f"Probing camera {camera_index}...")
            camera_info = self._probe_camera(camera_index)
            if camera_info is not None:
                detected_cameras.append(camera_info)

        self.finished.emit(detected_cameras)

    def _probe_camera(self, camera_index: int) -> Optional[Dict[str, Any]]:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap.release()
            return None

        try:
            for _ in range(self._warmup_frames):
                cap.read()

            start_time = time.perf_counter()
            first_valid_frame_elapsed_seconds: Optional[float] = None
            valid_frame = None

            while time.perf_counter() - start_time < self._probe_timeout_seconds:
                success, frame = cap.read()
                if success and frame is not None and getattr(frame, "size", 0) > 0:
                    valid_frame = frame
                    first_valid_frame_elapsed_seconds = time.perf_counter() - start_time
                    break
                time.sleep(self._frame_retry_sleep_seconds)

            if valid_frame is None:
                logger.debug("Skipping camera %s because no valid frames arrived within %.2fs", camera_index, self._probe_timeout_seconds)
                return None

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            backend = cap.getBackendName() if hasattr(cap, "getBackendName") else ""
            slow_start = bool(
                first_valid_frame_elapsed_seconds is not None
                and first_valid_frame_elapsed_seconds > self._slow_start_threshold_seconds
            )

            if slow_start:
                logger.info(
                    "Camera %s validated with slow start (first valid frame in %.2fs)",
                    camera_index,
                    first_valid_frame_elapsed_seconds,
                )

            return {
                "index": camera_index,
                "name": f"Camera {camera_index}",
                "width": width,
                "height": height,
                "fps": fps,
                "backend": backend,
                "slow_start": slow_start,
            }
        except Exception:
            logger.exception("Camera probe failed for index %s", camera_index)
            return None
        finally:
            cap.release()
