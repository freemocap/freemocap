import cv2

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
# cap = cv2.VideoCapture(2, cv2.CAP_ANY)

cap.set(cv2.CAP_PROP_EXPOSURE, -7)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 10800)

cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) 

while True:
    success, image = cap.read()
    cv2.imshow('blah', image)
    exit_key = cv2.waitKey(1)
    if exit_key ==27:
        break

cap.release()
cv2.destroyAllWindows()

