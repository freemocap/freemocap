from src.cameras.capture.frame_payload import FramePayload
from src.core_processor.board_detection.board_detection import BoardDetection


class CameraCalibration:
    def __init__(self, board_detection: BoardDetection):
        self._bd = board_detection

    def perform_calibration(self):
        self._bd.process(
            show_window=True,
            post_processed_frame_cb=self._calibration_work,
        )

    def _calibration_work(self, frame: FramePayload):
        print("found frame", frame.timestamp)


if __name__ == "__main__":
    a = BoardDetection()
    b = CameraCalibration(a)
    b.perform_calibration()
