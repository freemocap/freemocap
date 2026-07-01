"""A mock camera group for realtime-pipeline tests.

The realtime pipeline is built around a live ``CameraGroup``, but it only ever
reads four things off it: ``ipc.global_kill_flag``, ``configs``, ``id`` and
``shm.to_dto()``. The camera nodes and aggregator then ``recreate()`` the *real*
skellycam shared memory from that DTO.

So instead of mocking the shared memory, we create the **real**
``CameraGroupSharedMemory`` and feed it frames read from recorded videos — the
camera nodes, aggregator, triangulation, filtering and skeleton-fitting all run
unmodified. We fake only the camera-capture step, not the IPC / shm / processing
path. (Camera capture itself is trusted and not under test here.)

``MockCameraGroup`` subclasses the real ``CameraGroup`` so it satisfies the
``camera_group: CameraGroup`` beartype hints on the pipeline factories, but is
constructed via ``object.__new__`` to bypass the heavy (beartyped) dataclass
``__init__`` — we set only the attributes the realtime pipeline actually reads.
"""
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
from skellycam.core.camera.config.image_resolution import ImageResolution
from skellycam.core.camera.config.image_rotation_types import RotationTypes
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory
from skellycam.core.timestamps.timebase_mapping import TimebaseMapping
from skellycam.core.types.frame_dtype_factories import create_frame_dtype
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.utilities.create_camera_group_id import create_camera_group_id

from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper


def build_camera_configs_from_videos(video_group: VideoGroupHelper) -> CameraConfigs:
    """One CameraConfig per video, matching each video's actual resolution.

    The shm image shape is derived from these configs, so they MUST match the
    frames we later write or ``put_frame`` will raise on a dtype/shape mismatch.
    """
    configs: CameraConfigs = {}
    for index, (camera_id, helper) in enumerate(video_group.videos.items()):
        meta = helper.metadata
        configs[camera_id] = CameraConfig(
            camera_id=camera_id,
            camera_index=index,
            resolution=ImageResolution(width=meta.width, height=meta.height),
            color_channels=3,
            rotation=RotationTypes.NO_ROTATION,
        )
    return configs


@dataclass
class _MockCameraGroupIPC:
    """Stand-in for CameraGroupIPC.

    ``CameraGroup.id`` reads ``ipc.group_id``; ``RealtimePipeline.create`` reads
    ``ipc.global_kill_flag``. Those two are the entire surface we need.
    """
    global_kill_flag: object
    group_id: str


class MockCameraGroup(CameraGroup):
    """Subclass of CameraGroup that feeds recorded-video frames into real shm."""

    @classmethod
    def create(cls, *, synchronized_videos_dir, global_kill_flag) -> "MockCameraGroup":
        paths = sorted(str(p) for p in Path(synchronized_videos_dir).glob("*.mp4"))
        if not paths:
            raise FileNotFoundError(f"No .mp4 videos found in {synchronized_videos_dir}")
        # close_videos=False: we need the VideoHelpers to stay open for frame reads.
        video_group = VideoGroupHelper.from_video_paths(paths, close_videos=False)
        configs = build_camera_configs_from_videos(video_group)
        timebase_mapping = TimebaseMapping()
        shm = CameraGroupSharedMemory.create(
            camera_configs=configs,
            timebase_mapping=timebase_mapping,
            read_only=False,
        )

        # Bypass the (beartyped) dataclass __init__ and set only what we need.
        self = object.__new__(cls)
        self.ipc = _MockCameraGroupIPC(
            global_kill_flag=global_kill_flag,
            group_id=create_camera_group_id(),
        )
        self.configs = configs
        self.cameras = None  # unused: realtime create/start/driver never touch it
        self.shm = shm
        self.started = True  # so RealtimePipeline.start() skips camera_group.start()
        self._audio_recorder = None
        # mock-only state
        self._video_group = video_group
        self._timebase_mapping = timebase_mapping
        self._frame_recarrays: dict[CameraIdString, np.recarray] = {}
        return self

    # ``id`` and ``camera_ids`` are inherited from CameraGroup (read ipc.group_id
    # and configs respectively), so we don't redefine them.

    @property
    def frame_count(self) -> int:
        return self._video_group.frame_count

    def start(self) -> None:
        # shm is created eagerly in ``create``; nothing to start.
        self.started = True

    def _recarray_for(self, camera_id: CameraIdString) -> np.recarray:
        """One reusable frame recarray per camera, with camera_info baked in.

        Mirrors how a real camera sets up its frame buffer once (see
        ``CameraSharedMemoryRingBuffer.from_config``) and only mutates the image,
        frame number and timestamps per frame.
        """
        rec = self._frame_recarrays.get(camera_id)
        if rec is None:
            config = self.configs[camera_id]
            rec = np.recarray(1, dtype=create_frame_dtype(config))
            rec.frame_metadata.camera_info = config.to_frame_camera_info()[0]
            rec.frame_metadata.timebase_mapping = self._timebase_mapping.to_numpy_record_array()[0]
            self._frame_recarrays[camera_id] = rec
        return rec

    def write_frame(self, frame_index: int) -> None:
        """Read ``frame_index`` from every video and write it into shared memory.

        Frames are written sequentially from 0, so the ring-buffer write index
        equals ``frame_index`` and the metadata frame_number matches what the
        aggregator requests (``latest_multiframe_number``).
        """
        for camera_id, helper in self._video_group.videos.items():
            image = helper.read_frame_number(frame_index)
            config = self.configs[camera_id]
            if image.shape != config.image_shape:
                raise ValueError(
                    f"Camera {camera_id} frame {frame_index} has shape {image.shape}, "
                    f"expected {config.image_shape}"
                )
            rec = self._recarray_for(camera_id)
            rec.image[0] = image
            rec.frame_metadata.frame_number[0] = frame_index
            now_ns = time.perf_counter_ns()
            rec.frame_metadata.timestamps.pre_frame_grab_ns[0] = now_ns
            rec.frame_metadata.timestamps.post_frame_grab_ns[0] = now_ns
            rec.frame_metadata.timestamps.pre_copy_to_camera_shm_ns[0] = now_ns
            rec.frame_metadata.timestamps.post_copy_to_camera_shm_ns[0] = now_ns
            self.shm.camera_shms[camera_id].put_frame(frame_rec_array=rec, overwrite=True)

    def close(self) -> None:
        try:
            self.shm.unlink_and_close()
        finally:
            self._video_group.close()

    def __repr__(self) -> str:
        # Cheap repr: NEVER recurse into the multi-GB shm / numpy ring buffers.
        # (A giant recursive repr here previously blew the C stack when beartype
        # tried to format a type-violation error.)
        return (
            f"MockCameraGroup(id={self.ipc.group_id!r}, "
            f"camera_ids={list(self.configs.keys())})"
        )
