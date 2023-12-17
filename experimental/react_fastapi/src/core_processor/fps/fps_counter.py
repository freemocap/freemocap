import time
from typing import Dict, List


class FPSCounter:
    _num_frames_processed: int
    _start_time: float

    def __init__(self):
        self._start_time = 0
        self._num_frames_processed = 0

    def is_started(self):
        return self._start_time > 0

    def start(self):
        self._start_time = time.time()

    @property
    def current_fps(self):
        if self.elapsed() <= 0:
            return 0
        if self._num_frames_processed <= 0:
            return 0
        return self._num_frames_processed / self.elapsed()

    def elapsed(self):
        return time.time() - self._start_time

    def increment_frame_processed(self):
        self._num_frames_processed += 1


class FPSCamCounter:
    def __init__(self, webcam_ids: List[str]):
        self._webcam_ids = webcam_ids
        self._counters: Dict[str, FPSCounter] = self._init_counters(webcam_ids)

    def _init_counters(self, webcam_ids: List[str]):
        d = {}
        for webcam_id in webcam_ids:
            d[webcam_id] = FPSCounter()

        return d

    def increment_frame_processed_for(self, webcam_id):
        self._counters[webcam_id].increment_frame_processed()

    def current_fps_for(self, webcam_id):
        return self._counters[webcam_id].current_fps

    def start_all(self):
        for webcam_id in self._webcam_ids:
            self.start_for(webcam_id)

    def start_for(self, webcam_id):
        if self._counters[webcam_id].is_started():
            return

        self._counters[webcam_id].start()
