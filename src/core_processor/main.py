#!/usr/bin/env python

import asyncio
from typing import List, Optional

from freemocap.prod.cam.detection.cam_detection import DetectPossibleCameras
from src.core_processor.app_events.event_notify import EventNotifier
from src.core_processor.log_setup import logging_setup
from src.core_processor.ws_connection import WSConnection

loop = asyncio.get_event_loop()


async def begin_webcam_capture(webcam_ids: Optional[List[str]] = None):
    if not webcam_ids:
        cams = DetectPossibleCameras().find_available_cameras().cams_to_use
        webcam_ids = [cam.port_number for cam in cams]

    main_conn = WSConnection()
    tasks = [
        loop.create_task(main_conn.connect(wb_id))
        for wb_id in webcam_ids
    ]

    notify_coroutine = EventNotifier(webcam_ids).notify_all_subscribers()
    tasks.append(
        loop.create_task(notify_coroutine)
    )

    await asyncio.wait_for(
        asyncio.gather(*tasks),
        timeout=None,
    )


if __name__ == "__main__":
    logging_setup()
    loop.run_until_complete(begin_webcam_capture())
