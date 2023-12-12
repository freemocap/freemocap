from typing import Dict

import cv2

aruco_marker_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

number_of_squares_width = 7
number_of_squares_height = 5
black_square_side_length = 1
aruco_marker_length_proportional = .8

charuco_board_object = cv2.aruco.CharucoBoard(size=[number_of_squares_width, number_of_squares_height],
                                              squareLength=black_square_side_length,
                                              markerLength=aruco_marker_length_proportional,
                                              dictionary=aruco_marker_dict,
                                              )
number_of_charuco_corners = (number_of_squares_width - 1) * (number_of_squares_height - 1)
