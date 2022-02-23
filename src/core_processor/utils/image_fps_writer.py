import cv2


def write_fps_to_image(image, fps_number):
    cv2.putText(
        image,
        f"FPS: {str(fps_number)}",
        (10, 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (209, 180, 0, 255),
        1,
    )
