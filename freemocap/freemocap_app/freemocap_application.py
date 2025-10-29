import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraGroupIdString, MultiframeTimestampFloat, CameraIdString
from skellycam.skellycam_app.skellycam_app import SkellycamApplication, create_skellycam_app

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.core.pipeline.pipeline_manager import PipelineManager
from freemocap.core.pubsub.pubsub_topics import AggregationNodeOutputMessage
from freemocap.core.tasks.calibration_task.calibration_helpers.charuco_serializer import CharucoOverlayData
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


@dataclass
class FreemocApp:
    global_kill_flag: multiprocessing.Value
    pipeline_shutdown_event: multiprocessing.Event
    skellycam_app: SkellycamApplication
    pipeline_manager: PipelineManager

    @classmethod
    def create(cls, global_kill_flag: multiprocessing.Value):
        skellycam_app = create_skellycam_app(global_kill_flag=global_kill_flag)
        pipeline_manager = PipelineManager(global_kill_flag=global_kill_flag)
        return cls(global_kill_flag=global_kill_flag,
                   pipeline_shutdown_event=multiprocessing.Event(),
                   skellycam_app=skellycam_app,
                   pipeline_manager=pipeline_manager,
                   )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    @property
    def camera_group_manager(self):
        return self.skellycam_app.camera_group_manager

    def connect_pipeline(self,
                         camera_group: CameraGroup,
                         pipeline_config: PipelineConfig) -> tuple[CameraGroupIdString, PipelineIdString]:
        pipeline = self.pipeline_manager.create_pipeline(camera_group=camera_group, pipeline_config=pipeline_config)
        return camera_group.id, pipeline.id

    def disconnect_pipeline(self):
        self.pipeline_manager.close_all_pipelines()

    def get_latest_frontend_payloads(self, if_newer_than: FrameNumberInt) -> tuple[
        dict[CameraGroupIdString, tuple[FrameNumberInt, bytes]], dict[PipelineIdString, dict[CameraIdString, CharucoOverlayData]]]:
        # TODO - this is a mess, needs clean up
        if len(self.pipeline_manager.pipelines) == 0:
            camera_group_frame_bytearrays: dict[CameraGroupIdString, tuple[FrameNumberInt,bytes]] = {}
            for camera_group_id, camera_group in self.camera_group_manager.camera_groups.items():
                out = camera_group.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if out is not None:
                    frame_number,_, frames_bytearray = out
                    camera_group_frame_bytearrays[camera_group_id] = (frame_number,frames_bytearray)
            return camera_group_frame_bytearrays, {}

        pipeline_outputs: dict[
            PipelineIdString, AggregationNodeOutputMessage] = self.pipeline_manager.get_latest_output()
        camera_group_frame_bytearrays: dict[CameraGroupIdString, tuple[FrameNumberInt,bytes]] = {}
        for pipeline_id, agg_node_output in pipeline_outputs.items():
            camera_group = self.camera_group_manager.camera_groups.get(agg_node_output.camera_group_id, None)
            if camera_group is None:
                logger.error(f"Camera group (id:{agg_node_output.camera_group_id})for pipeline ID {agg_node_output.pipeline_id} not found!!")
                #might should fail on this, but for now just shout and skip
                continue
            frames_bytearray  = camera_group.get_frontend_payload_by_frame_number(frame_number=agg_node_output.frame_number)
            camera_group_frame_bytearrays[agg_node_output.camera_group_id] = (agg_node_output.frame_number,frames_bytearray)

        pipeline_overlays: dict[PipelineIdString, dict[CameraIdString, CharucoOverlayData]] = {pipeline_id: {} for
                                                                                               pipeline_id in
                                                                                               pipeline_outputs.keys()}
        for p_id, agg_node_output in pipeline_outputs.items():
            pipeline_overlays[p_id] = {camera_id: CharucoOverlayData.from_charuco_observation(camera_id=camera_id,
                                                                                              observation=camera_node_output.charuco_observation)
                                       for camera_id, camera_node_output in agg_node_output.camera_node_outputs.items()}
        return camera_group_frame_bytearrays, pipeline_overlays

    def close(self):
        self.global_kill_flag.value = True
        self.pipeline_shutdown_event.set()
        self.pipeline_manager.close_all_pipelines()
        self.skellycam_app.shutdown_skellycam() if self.skellycam_app else None


FREEMOCAP_APP: FreemocApp | None = None


def create_freemocap_app(global_kill_flag: multiprocessing.Value) -> FreemocApp:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        FREEMOCAP_APP = FreemocApp.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("FreemocApp already exists!")
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocApp:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise ValueError("FreemocApp does not exist!")
    return FREEMOCAP_APP
