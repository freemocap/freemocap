import cv2
import time

NUMBER_OF_USB_PORTS_TO_CHECK = 20
NUMBER_OF_FRAMES_TO_GRAB = 10

for port_number in range(NUMBER_OF_USB_PORTS_TO_CHECK):
    cap = cv2.VideoCapture(port_number)
    time_start = time.perf_counter()
    success, image = cap.read()
    time_end = time.perf_counter()
    time_elapsed = time_end - time_start
    print(
        f"Trying to read an image from port  {port_number} took {time_elapsed:.3} seconds and yielded: success={success}, image.__class__ ={image.__class__}"
    )
    if success:
        for frame_number in range(NUMBER_OF_FRAMES_TO_GRAB):
            try:

                time_start = time.perf_counter()
                success, image = cap.read()
                time_end = time.perf_counter()
                time_elapsed = time_end - time_start
                print(
                    f"Camera port: {port_number}, Capture Object: {cap},  Frame# {frame_number}, frame grab duration: {time_elapsed:.3f} seconds, image.shape:{image.shape}"
                )
            except Exception as e:
                print(e)
                raise e
    cap.release()
