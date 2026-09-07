import multiprocessing
import time
import unittest
from concurrent.futures import Future
from unittest.mock import Mock, patch

import numpy as np

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.inference_service import InferenceMode, InferenceRequest, InferenceService
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import RealtimeSkeletonInferenceNode
from freemocap.pubsub.pubsub_topics import ProcessFrameNumberMessage
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemoryDTO
from skellycam.core.ipc.shared_memory.camera_shared_memory_ring_buffer import CameraSharedMemoryRingBuffer
from skellytracker.core.data_primitives.observation import Observation


class RealtimeInferenceAdapterTests(unittest.TestCase):
    def test_adapter_submits_to_service_and_publishes_matching_results(self) -> None:
        for detector in ("rtmpose", "mediapipe"):
            with self.subTest(detector=detector):
                queues = [multiprocessing.Queue() for _ in range(5)]
                requests, configs, results, timings, logs = queues
                ipc = PipelineIPC(pipeline_id="live", ws_queue=logs,
                    global_kill_flag=multiprocessing.Value("b", False),
                    heartbeat_timestamp=multiprocessing.Value("d", time.perf_counter()))
                service = Mock(spec=InferenceService)
                client = service.register.return_value
                client.failure = None
                camera_ids = ["left", "right", "overhead"]
                dto = Mock(spec=CameraGroupSharedMemoryDTO)
                dto.camera_shm_dtos = dict.fromkeys(camera_ids, Mock())
                images = [np.zeros((8, 12, 3), dtype=np.uint8) for _ in camera_ids]

                def infer(request: InferenceRequest) -> Future[dict[str, Observation]]:
                    future: Future[dict[str, Observation]] = Future()
                    future.set_result({key: Observation(frame_number=request.frame_number,
                        image_size=image.shape[:2], stages={}) for key, image in request.images.items()})
                    ipc.shutdown_pipeline()
                    return future

                client.submit.side_effect = infer
                config = RealtimePipelineConfig(log_pipeline_times=False,
                    camera_node_config={"detector_type": detector})
                requests.put(ProcessFrameNumberMessage(frame_number=7))
                try:
                    with patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.CameraGroupSharedMemory.recreate"), \
                         patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node.CameraSharedMemoryRingBuffer.recreate", return_value=Mock(spec=CameraSharedMemoryRingBuffer)), \
                         patch("freemocap.core.pipeline.realtime.realtime_skeleton_inference_node._read_frames", return_value=(images, camera_ids)):
                        RealtimeSkeletonInferenceNode._run(camera_group_id="group", camera_ids=camera_ids,
                            pipeline_config=config, ipc=ipc, shutdown_self_flag=multiprocessing.Value("b", False),
                            camera_group_shm_dto=dto, process_frame_number_sub=requests,
                            pipeline_config_sub=configs, skeleton_result_pub=results, timing_pub=timings,
                            inference_service=service)
                    result = results.get(timeout=2)
                    self.assertEqual(result.frame_number, 7)
                    self.assertEqual(set(result.per_camera_skeleton), set(camera_ids))
                    registration = service.register.call_args.args[0]
                    self.assertEqual(registration.mode, InferenceMode.REALTIME)
                    self.assertEqual(registration.pipeline_id, ipc.pipeline_id)
                    client.close.assert_called_once()
                finally:
                    for queue in queues:
                        queue.close()
                        queue.join_thread()


if __name__ == "__main__":
    unittest.main()

