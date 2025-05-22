from dataclasses import dataclass
from typing import Dict

import cv2


@dataclass
class CharucoBoardDefinition:
    name: str
    number_of_squares_width: int
    number_of_squares_height: int
    black_square_side_length: int
    aruco_marker_length_proportional: float
    aruco_marker_dict: Dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

    def __post_init__(self):
        self.charuco_board = cv2.aruco.CharucoBoard(
            size=[self.number_of_squares_width, self.number_of_squares_height],
            squareLength=self.black_square_side_length,
            markerLength=self.aruco_marker_length_proportional,
            dictionary=self.aruco_marker_dict,
        )

        self.number_of_charuco_corners = (self.number_of_squares_width - 1) * (self.number_of_squares_height - 1)


def full_charuco_board() -> CharucoBoardDefinition:
    return CharucoBoardDefinition(
        name="full_board_7x5",
        number_of_squares_width=7,
        number_of_squares_height=5,
        black_square_side_length=1,
        aruco_marker_length_proportional=0.8,
    )


def mini_charuco_board() -> CharucoBoardDefinition:
    return CharucoBoardDefinition(
        name="mini_board_5x3",
        number_of_squares_width=5,
        number_of_squares_height=3,
        black_square_side_length=1,
        aruco_marker_length_proportional=0.8,
    )


CHARUCO_BOARDS = {
    "Full Charuco Board (7x5)": full_charuco_board,
    "Mini Charuco Board (5x3)": mini_charuco_board,
}
