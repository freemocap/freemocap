import base64
import threading
import traceback
from queue import Queue

import orjson
from old_src.api.services.board_detect_service import BoardDetectService


def tryit():
    service = BoardDetectService()
    output_queue = Queue()
    t = threading.Thread(
        target=service.run_detection_on_cam_id, args=(output_queue,), daemon=True
    )
    t.start()

    while True:
        try:
            # success, frame = cv2.imencode('.png', image)
            image, webcam_id = output_queue.get(timeout=1)
            if image is not None:
                d = orjson.dumps({"frame": str(base64.b64encode(image.tobytes()))})
        except:
            traceback.print_exc()


if __name__ == "__main__":
    tryit()
