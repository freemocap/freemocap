from dataclasses import dataclass
from typing import Dict

import cv2
import numpy as np


@dataclass
class CharucoBoardDataClass:
    aruco_marker_dict: Dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
    number_of_squares_width: int = 5
    number_of_squares_height: int = 3
    black_square_side_length: int = 1
    aruco_marker_length_proportional: float = 0.8

    def __post_init__(self):
        self.charuco_board = cv2.aruco.CharucoBoard_create(
            self.number_of_squares_width,
            self.number_of_squares_height,
            self.black_square_side_length,
            self.aruco_marker_length_proportional,
            self.aruco_marker_dict,
        )

        self.number_of_charuco_corners = (self.number_of_squares_width - 1) * (
            self.number_of_squares_height - 1
        )
