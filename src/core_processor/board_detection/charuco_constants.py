import cv2

aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
charuco_length = 7
charuco_width = 5

board = cv2.aruco.CharucoBoard_create(charuco_length, charuco_width, 1, 0.8, aruco_dict)
num_charuco_corners = (charuco_length - 1) * (charuco_width - 1)
