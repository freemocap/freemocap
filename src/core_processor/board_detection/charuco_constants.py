import cv2

aruco_marker_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
number_of_squares_width = 7
number_of_squares_height = 5

charuco_board_object = cv2.aruco.CharucoBoard_create(number_of_squares_width, number_of_squares_height, 1, 0.8, aruco_marker_dict)
number_of_charuco_corners = (number_of_squares_width - 1) * (number_of_squares_height - 1)
