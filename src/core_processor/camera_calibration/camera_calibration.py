from src.cameras.capture.frame_payload import FramePayload
from src.core_processor.board_detection.board_detection import BoardDetection, CharucoFramePayload


class CameraCalibration:
    def __init__(self, board_detection: BoardDetection):
        self._bd = board_detection

    def perform_calibration(self):
        self._bd.process(
            show_window=True,
            save_video=True,
            post_processed_frame_cb=self._calibration_work,
        )

    def _calibration_work(self, webcam_id: str, charuco_frame_payload: CharucoFramePayload):
        print(f"found frame from camera {webcam_id} at timestamp {charuco_frame_payload.annotated_frame_payload.timestamp/1e9}")


if __name__ == "__main__":
    print('start main')
    a = BoardDetection()
    b = CameraCalibration(a)
    b.perform_calibration()
