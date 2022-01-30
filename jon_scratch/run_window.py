import time
import cv2

while True:
    cv2.namedWindow("test")
    key = cv2.waitKey(0)
    if key == 27:
        break
