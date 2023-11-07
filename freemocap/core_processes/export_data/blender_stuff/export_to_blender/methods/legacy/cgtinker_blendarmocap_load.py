import logging
import sys

from BlendArMocap.src.cgt_freemocap.fm_subprocess_cmd_receiver import import_freemocap_session

logger = logging.getLogger(__name__)

argv = sys.argv
argv = argv[argv.index("--") + 1 :]
recording_path = argv[0]
blender_save_path = argv[1]
bind_to_rig_bool = bool(argv[2])
load_synchronized_videos_bool = bool(argv[3])
timeout = bool(argv[4])
load_raw_bool = bool(argv[5])
load_quick_bool = bool(argv[6])

logger.info(
    f"Invoking CGTinker's BlendArMocap based export method with arguments -"
    f"\nrecording_path: {recording_path}, "
    f"\nblender_save_path: {blender_save_path}, "
    f"\nbind_to_rig_bool: {bind_to_rig_bool}, "
    f"\nload_synchronized_videos_bool: {load_synchronized_videos_bool}, "
    f"\ntimeout: {timeout}, "
    f"\nload_raw_bool: {load_raw_bool}, "
    f"\nload_quick_bool: {load_quick_bool}"
)

import_freemocap_session(
    session_directory=recording_path,
    bind_to_rig=bind_to_rig_bool,
    load_synch_videos=load_synchronized_videos_bool,
    timeout=timeout,
    load_raw=load_raw_bool,
    load_quick=load_quick_bool,
)
