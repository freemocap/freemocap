#!/usr/bin/env python
import asyncio
import logging
from typing import List, Optional

from aiomultiprocess.core import Process, get_manager

from freemocap.prod.cam.detection.cam_detection import DetectPossibleCameras
from src.core_processor.app_events.app_queue import AppQueue
from src.core_processor.app_events.event_notify import EventNotifier
from src.core_processor.log_setup import logging_setup
from src.core_processor.ws_connection import WSConnection

logger = logging.getLogger(__name__)


async def start(webcam_id: str, queue):
    logging_setup()
    main_conn = WSConnection()
    await main_conn.connect(webcam_id, queue)


async def begin_realtime_processing(webcam_ids: Optional[List[str]] = None):
    if not webcam_ids:
        cams = DetectPossibleCameras().find_available_cameras().cams_to_use
        webcam_ids = [cam.webcam_id for cam in cams]

    manager = get_manager()
    app_queue = AppQueue(manager)
    app_queue.create_all(webcam_ids)

    tasks = []
    for webcam_id in webcam_ids:
        queue = app_queue.get_by_webcam_id(webcam_id)
        p = Process(target=start, args=(webcam_id, queue))
        p.start()
        tasks.append(p.join())

    ev = EventNotifier(webcam_ids)
    # for webcam_id in webcam_ids:
    #     queue = app_queue.get_by_webcam_id(webcam_id)
    #     p = Process(target=ev.notify_all_subscribers, args=(queue,))
    #     p.start()
    #     tasks.append(p.join())

    logger.info(f"Process count: {len(tasks)}")
    return await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(begin_realtime_processing())
