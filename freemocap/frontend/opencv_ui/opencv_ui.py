import logging
import multiprocessing
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import cv2

logger = logging.getLogger(__name__)

# Constants for key actions
KEY_SHOW_CONTROLS = ord("h")
KEY_SHOW_OVERLAY = ord("o")
KEY_SHOW_INFO = ord("i")
KEY_SET_AUTO_EXPOSURE = ord("a")
KEY_INCREASE_EXPOSURE = ord("w")
KEY_DECREASE_EXPOSURE = ord("s")
KEY_RESET_EXPOSURE = ord("r")
KEY_PAUSE_SPACE = ord(" ")
KEY_PAUSE_P = ord("p")
KEY_QUIT_Q = ord("q")
KEY_QUIT_ESC = 27


class ExposureModes(float, Enum):
    AUTO = 0.75  # Default value to activate auto exposure mode
    MANUAL = 0.25  # Default value to activate manual exposure mode


@dataclass
class OpencvUI(threading.Thread):
    show_controls: bool = False
    paused: bool = False
    show_overlay: bool = True
    show_info: bool = True
    show_watermark: bool = True

    frame_durations = deque(maxlen=30)
    tracker_durations = deque(maxlen=30)
    annotation_durations = deque(maxlen=30)

    window_title: str = f"FreeMoCap"

    image_input_queue: multiprocessing.Queue = field(default_factory=multiprocessing.Queue)
    shutdown_event: multiprocessing.Event = field(default_factory=multiprocessing.Event)

    def _show_overlay(self, image, text):
        """
        Overlay text on the image.
        """

        y0, dy = 30, 25  # y0 - initial y value, dy - offset between lines
        x0 = 6
        number_of_lines = text.count("\n") + 1
        longest_line = max(text.split("\n"), key=len)
        rect_horizontal_edge_length = len(longest_line) * 10
        rect_vertical_edge_length = dy * number_of_lines + 10
        rect_upper_left_coordinates = (int(x0 / 2), int(y0 / 2))
        rect_lower_right_coordinates = (
            int(x0 / 2) + rect_vertical_edge_length, int(x0 / 2) + rect_horizontal_edge_length)
        rect_color_and_transparency = (25, 25, 25, .2)
        # cv2.rectangle(image, rect_upper_left_coordinates, rect_lower_right_coordinates, rect_color_and_transparency, -1)

        for i, line in enumerate(text.split("\n")):
            y = y0 + i * dy
            self.draw_doubled_text(image, line, x0, y, 0.7, (255, 15, 210), 1)

    def draw_doubled_text(self, image, text, x, y, font_scale, color, thickness):
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness + 2)
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)

    def run(self):
        cv2.namedWindow(self.window_title)

        tik = time.perf_counter()
        while not self.shutdown_event.is_set():
            if not self.image_input_queue.empty():
                queue_grab_tik = time.perf_counter()
                payload = self.image_input_queue.get()
                queue_grab_tok =time.perf_counter()

                if not self.paused:
                    tok = time.perf_counter()
                    self.frame_durations.append(tok - tik)
                    tik = tok


                    # # Get the window size
                    # _, _, window_width, window_height = cv2.getWindowImageRect(self.window_title)
                    # # Resize the image to fit the window
                    # annotated_image = cv2.resize(annotated_image, (window_width, window_height))

                key = cv2.waitKey(1) & 0xFF
                if key == KEY_QUIT_Q or key == KEY_QUIT_ESC:
                    self.shutdown_event.set()
                    break
                elif key == KEY_PAUSE_SPACE or key == KEY_PAUSE_P:
                    self.paused = not self.paused
                elif key == KEY_SHOW_OVERLAY:
                    self.show_overlay = not self.show_overlay
                elif key == KEY_SHOW_INFO:
                    self.show_info = not self.show_info
                elif key == KEY_SHOW_CONTROLS:
                    show_controls = not show_controls

                mean_frame_duration = sum(self.frame_durations) / len(self.frame_durations)
                mean_frames_per_second = 1 / mean_frame_duration
                overlay_string = ""
                info_string = ""
                info_string += f"Mean UI FPS : {mean_frames_per_second:.2f}\n"
                info_string += f"Mean UI update duration: {mean_frame_duration * 1000:.2f} ms\n"
                if self.show_info:
                    overlay_string += info_string
                if self.show_controls:
                    overlay_string += (
                        "Controls:\n"
                        f"'SPACE'/'{chr(KEY_PAUSE_P)}': pause\n"
                        f"'{chr(KEY_SHOW_INFO)}': {'show info' if not self.show_info else "hide info"}\n"
                        f"'{chr(KEY_SHOW_OVERLAY)}': show overlay\n"
                        f"'{chr(KEY_SET_AUTO_EXPOSURE)}': auto-exposure\n"
                        f"'{chr(KEY_INCREASE_EXPOSURE)}'/'{chr(KEY_DECREASE_EXPOSURE)}': exposure +/-\n"
                        f"'{chr(KEY_RESET_EXPOSURE)}': reset\n"
                        f"'ESC/{chr(KEY_QUIT_Q)}': quit\n"
                        f"'{chr(KEY_SHOW_CONTROLS)}': hide controls"
                    )
                else:
                    overlay_string += f"'{chr(KEY_SHOW_CONTROLS)}': show controls"

                self._show_overlay(
                    payload.annotated_image,
                    overlay_string,
                )
                cv2.imshow(self.window_title, annotated_image)

        cap.release()
        cv2.destroyAllWindows()
