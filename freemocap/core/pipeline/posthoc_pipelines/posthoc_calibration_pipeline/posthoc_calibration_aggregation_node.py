import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import TopicSubscriptionQueue

from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationpipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.charuco_model_from_observations import \
    charuco_model_from_observations
from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoMetadata
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.charuco_observation_aggregator import \
    anipose_calibration_from_charuco_observations

from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder

from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.shared_view_accumulator import CharucoObservations
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt, VideoIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputMessage, VideoNodeOutputTopic
from freemocap.utilities.wait_functions import wait_1ms

logger = logging.getLogger(__name__)


class PosthocAgregationNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    config: RealtimePipelineConfig
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class PosthocCalibrationAggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               calibration_pipeline_config: CalibrationpipelineConfig,
               video_metadata: dict[VideoIdString, VideoMetadata],
               pipeline_id: PipelineIdString,
               recording_info: RecordingInfo,
               subprocess_registry: list[multiprocessing.Process],
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"Pipeline-{pipeline_id}-PosthocAggregationNode",
                                         kwargs=dict(calibration_pipeline_config=calibration_pipeline_config,
                                                     pipeline_id=pipeline_id,
                                                     recording_info=recording_info,
                                                     video_metadata=video_metadata,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     video_node_subscription=ipc.pubsub.topics[
                                                         VideoNodeOutputTopic].get_subscription(),
                                                     ),

                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(calibration_pipeline_config: CalibrationpipelineConfig,
             recording_info: RecordingInfo,
             pipeline_id: PipelineIdString,
             video_metadata: dict[VideoIdString, VideoMetadata],
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             video_node_subscription: TopicSubscriptionQueue,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        start_frame = set(vm.start_frame for vm in video_metadata.values())
        end_frame = set(vm.end_frame for vm in video_metadata.values())
        if len(start_frame) != 1 or len(end_frame) != 1:
            raise ValueError(f"Mismatch in start/end frames across videos in pipeline {pipeline_id}: "
                             f"start_frames={start_frame}, end_frames={end_frame}")
        start_frame = start_frame.pop()
        end_frame = end_frame.pop()
        frame_numbers = set(range(start_frame, end_frame))
        video_ids = list(video_metadata.keys())

        logger.debug(f"PosthocCalibrationAggregationNode for pipeline id: '{pipeline_id}' starting main loop")
        try:

            video_outputs_by_frame: dict[FrameNumberInt, dict[VideoIdString, VideoNodeOutputMessage | None]] = {
                frame_number: {video_id: None for video_id in video_ids}
                for frame_number in frame_numbers
            }
            got_all_outputs_by_frame = {frame_number: False for frame_number in frame_numbers}

            if not len(video_outputs_by_frame) == len(frame_numbers):
                raise ValueError(f"Mismatch between video outputs by frame and recording info frame count - "
                                 f"{len(video_outputs_by_frame)} vs {len(frame_numbers)}")

            while not shutdown_self_flag.value and ipc.should_continue:
                wait_1ms()
                if not video_node_subscription.empty():
                    video_node_output_message: VideoNodeOutputMessage = video_node_subscription.get()

                    if not video_node_output_message.video_id in video_ids:
                        raise ValueError(
                            f"Video ID {video_node_output_message.video_id} not in recording info for pipeline {pipeline_id} - {recording_info.recording_name}")
                    video_outputs_by_frame[video_node_output_message.frame_number][
                        video_node_output_message.video_id] = video_node_output_message
                    if all([isinstance(value, VideoNodeOutputMessage) for value in
                           video_outputs_by_frame[video_node_output_message.frame_number].values()]):
                        logger.info(f"Received all video node outputs for frame {video_node_output_message.frame_number} in pipeline {pipeline_id}")
                        got_all_outputs_by_frame[video_node_output_message.frame_number] = True

                if all(list(got_all_outputs_by_frame.values())):
                    break
            logger.info(f"All video node outputs received for pipeline {pipeline_id}, starting calibration")
            charuco_observations_by_frame: list[CharucoObservations] = []
            for frame_outputs in video_outputs_by_frame.values():
                if not all([isinstance(output, VideoNodeOutputMessage) for output in frame_outputs.values()]):
                    raise ValueError(
                        f"Missing video node outputs for frame in pipeline {pipeline_id}: {frame_outputs}")
                charuco_observations_by_frame.append({
                    video_id: output.observation
                    for video_id, output in frame_outputs.items()
                })


            calibration_toml_path, triangulator = anipose_calibration_from_charuco_observations(
                charuco_observations_by_frame=charuco_observations_by_frame,
                calibration_pipeline_config=calibration_pipeline_config,
                recording_info=recording_info,
                video_metadata=video_metadata,
                # use_charuco_as_groundplane=True,
            )

            observation_recorders_by_video = {video_id: BaseRecorder() for video_id in video_ids}
            for frame_number, frame_outputs_by_video in video_outputs_by_frame.items():
                if not all([isinstance(output, VideoNodeOutputMessage) for output in frame_outputs_by_video.values()]):
                    raise ValueError(
                        f"Missing video node outputs for frame in pipeline {pipeline_id}: {frame_number}")
                for video_id, recorder in observation_recorders_by_video.items():
                    observation = frame_outputs_by_video[video_id].observation
                    recorder.add_observation(observation=observation)

            charuco_board_model = charuco_model_from_observations(
                observation_recorders=observation_recorders_by_video,
                calibration_toml_path=calibration_toml_path,
                output_data_folder=Path(recording_info.full_recording_path) / "output_data",
            )

            logger.success(
                f"Posthoc calibration completed for pipeline {pipeline_id}! Calibration file saved to {recording_info.full_recording_path}")


        except Exception as e:
            logger.error(f"Exception in PosthocAggregationNode for recording: {recording_info.recording_name}: {e}", exc_info=True)
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"Shutting down aggregation process for  recording: {recording_info.recording_name}")

    def start(self):
        logger.debug(f"Starting PosthocAggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping PosthocAggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()
