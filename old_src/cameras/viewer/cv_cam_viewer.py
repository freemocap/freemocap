import multiprocessing
from multiprocessing import Process
from typing import Union

import cv2

from old_src.cameras.capture.dataclasses.frame_payload import FramePayload


class CvCamViewer:
    def __init__(self):
        self._process: Process = None
        self._payload = None
        self._recv, self._send = multiprocessing.Pipe(duplex=False)

    @staticmethod
    def _begin(conn, webcam_id):
        while True:
            payload: FramePayload = conn.recv()
            if payload:
                cv2.imshow(str(webcam_id), payload.image)
                cv2.waitKey(1)

    def begin_viewer(self, webcam_id: Union[str, int]):
        self._process = Process(target=CvCamViewer._begin, args=(self._recv, webcam_id))

        self._process.start()

    def recv_img(self, frame_payload):
        self._send.send(frame_payload)
