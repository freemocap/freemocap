from dataclasses import dataclass
from typing import Dict

import cv2


@dataclass
class CharucoBoard:
    _aruco_marker_dict: Dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_250)
    _number_of_squares_width: int = 7
    _number_of_squares_height: int = 5
    _black_square_side_length: int = 1
    _aruco_marker_length_proportional: float = .8

    def __post_init__(self):
        self._charuco_board = cv2.aruco.CharucoBoard_create(self._number_of_squares_width,
                                                            self._number_of_squares_height,
                                                            self._black_square_side_length,
                                                            self._aruco_marker_length_proportional,
                                                            self._aruco_marker_dict)

        self._number_of_charuco_corners = (self._number_of_squares_width - 1) * (self._number_of_squares_height - 1)

    @property
    def charuco_board(self):
        return self._charuco_board

    @property
    def number_of_charuco_corners(self):
        return self._number_of_charuco_corners

    @property
    def aruco_marker_dict(self):
        return self._aruco_marker_dict
