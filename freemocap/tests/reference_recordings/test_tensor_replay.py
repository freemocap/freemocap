"""Exercise tensor admissions and channel layouts on the real realtime workers.

Uses the existing reference-video shared-memory replay, with human and ChArUco
tracking enabled. Filtering stays disabled for decimated 6-fps test_data. No GUI
or server is started. This is a correctness check, not a throughput benchmark.
"""

from dataclasses import replace
import multiprocessing
from multiprocessing import shared_memory
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue

from skellyforge.core.data_tensors import SourceIdentity
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig, OneEuroConfig
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup
from freemocap.core.pipeline.realtime.realtime_aggregator_node_config import RealtimeAggregatorNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.recording.exports.arrays import available_channels, ordered_arrays
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.core.skeletons.charuco_board_skeleton import CHARUCO_BOARD_MODEL_ID
from freemocap.core.skeletons.standard_human_skeleton import STANDARD_HUMAN_MODEL_ID, build_standard_human_bundle
from freemocap.core.streaming.producers.joint_angles_producer import JointAnglesProducer
from freemocap.core.streaming.producers.producer_contexts import FrameContext
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
from freemocap.tests.pipelines.mocks.mock_camera_group import MockCameraGroup
from freemocap.tests.pipelines.mocks.realtime_driver import drive_realtime_lockstep
from freemocap.tests.recording_datasets import synchronized_video_directory
from freemocap.tests.test_tensor_pipeline_integration import reference_structure, tracker_tensor
from freemocap.tools.datasets.preparation import file_digest


def _keypoint_stages(stages):
    for stage in stages.values():
        if stage.keypoints is not None:
            yield stage
        yield from _keypoint_stages(stage.children)


@unittest.skipUnless(os.environ.get("FREEMOCAP_PROVENANCE_PREPARED_ROOT"), "Set the prepared reference-data root")
class TensorReplayTests(unittest.TestCase):
    def test_reference_replay_preserves_tracker_buffers_and_authored_joint_layouts(self):
        # unittest does not run the pytest session fixture in tests/conftest.py.
        # Keep its idempotent logging setup, without closing the reusable global queue.
        log_queue = create_websocket_log_queue()
        self.addCleanup(log_queue.cancel_join_thread)
        structure = reference_structure()
        original_digest = file_digest(structure.data_parquet_path)
        calibration = find_recording_calibration(recording_folder=structure.full_path)
        self.assertIsNotNone(calibration)
        # Existing recorded source times only supply the stream producer's context.
        # The producer itself consumes angles, not timing; no live clock is inferred.
        with tempfile.TemporaryDirectory() as temporary, recording_view(structure.data_parquet_path) as view:
            run_id = view.metadata.selected_run_id
            item = next(entry for entry in available_channels(view.metadata.runs[run_id])
                        if entry[0].channel == "LANDMARKS_3D")
            with ordered_arrays(view, run_id, item, scratch=Path(temporary)) as arrays:
                np.testing.assert_array_equal(arrays.frames, np.arange(222))
                reference_times = arrays.timestamps.copy()
        config = RealtimePipelineConfig(
            camera_node_config=CameraNodeConfig(worker_mode=WorkerMode.THREAD,
                charuco_board=CharucoBoardDefinition.create_test_data_7x5(),
                charuco_tracking_enabled=True, skeleton_tracking_enabled=True),
            aggregator_config=RealtimeAggregatorNodeConfig(calibration_toml_path=str(calibration),
                triangulation_enabled=True, skeleton_fitting_enabled=True,
                center_of_mass_enabled=True, realtime_filter_config=RealtimeFilterConfig(spatial_smoothing=OneEuroConfig(enabled=False), velocity_gate_enabled=False, gap_duration_s=0.0, segment_retention_s=0.0)),
            use_centralized_inference=True, log_pipeline_times=False,
        )
        flag = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=flag, worker_mode=WorkerMode.THREAD)
        service = InferenceService(worker_registry=registry)
        manager = RealtimePipelineManager(worker_registry=registry, inference_service=service)
        group = None
        capture = None
        memory_names = []
        try:
            registry.start_heartbeat()
            group = MockCameraGroup.create(synchronized_videos_dir=synchronized_video_directory(structure.full_path),
                                           global_kill_flag=flag)
            for camera in group.shm.to_dto().camera_shm_dtos.values():
                for element in (camera.ring_shm_dto, camera.last_written_index_shm_dto, camera.last_read_index_shm_dto):
                    memory_names.extend((element.shm_name, element.shm_valid_name, element.first_written_shm_name))
            self.assertEqual(group.frame_count, 222)
            self.assertEqual(len(group.camera_ids), 3)
            capture = CaptureGroup(group, flag)
            self.assertIs(capture.shm, group.shm)
            service.start()
            pipeline = manager.create_pipeline(camera_group=capture, pipeline_config=config)
            driven = drive_realtime_lockstep(pipeline=pipeline, mock_group=group,
                                             num_frames=group.frame_count, per_frame_timeout=120.0)
            self.assertEqual([output.frame_number for output in driven.outputs], list(range(group.frame_count)))
            self.assertEqual(driven.frames_written, driven.frames_processed)
            self.assertIsNone(pipeline.failure)
            self.assertTrue(all(output.calibration_applicable for output in driven.outputs))
            self.assertTrue(all(set(output.camera_node_outputs) == set(group.camera_ids) for output in driven.outputs))
            self.assertTrue({CHARUCO_BOARD_MODEL_ID, STANDARD_HUMAN_MODEL_ID}.issubset(
                {model for output in driven.outputs for model in output.reconstructions}))
            checked_observations = set()
            for output in driven.outputs[::max(1, group.frame_count // 3)]:
                for camera_id, camera in output.camera_node_outputs.items():
                    self.assertEqual(camera.frame_number, output.frame_number)
                    for observation_kind in ("charuco_observation", "skeleton_observation"):
                        observation = getattr(camera, observation_kind)
                        if observation is None:
                            continue
                        for stage in _keypoint_stages(observation.stages):
                            source = SourceIdentity(source_id=f"{observation_kind}:{stage.name}",
                                                    sensor_group=group.id, camera_id=camera_id)
                            tensor = tracker_tensor(stage.keypoints, source)
                            self.assertIs(tensor.data_values, stage.keypoints.xyz)
                            self.assertIs(tensor.companion_values("confidence_scores"), stage.keypoints.visibility)
                            self.assertEqual(tensor.tensor_layout.axes[0].identifiers, stage.keypoints.names)
                            self.assertEqual(tensor.tensor_layout.source_identity.camera_id, camera_id)
                            self.assertEqual(tensor.tensor_layout.source_identity.instance_id, 0)
                            checked_observations.add(observation_kind)
            self.assertEqual(checked_observations, {"charuco_observation", "skeleton_observation"})
            bundle = build_standard_human_bundle(detector_type=config.camera_node_config.detector_type)
            expected_names = tuple(name for joint in bundle.skeleton.joints.values() for name in joint.angle_names)
            producer = JointAnglesProducer()
            output = next(output for output in driven.outputs
                          if STANDARD_HUMAN_MODEL_ID in output.reconstructions
                          and output.reconstructions[STANDARD_HUMAN_MODEL_ID].joint_angles)
            frame_context = FrameContext(frame_number=output.frame_number,
                timestamp=float(reference_times[output.frame_number]), aggregator_output=output)
            channel, = producer.fill(frame_context, bundle)
            self.assertEqual(channel.names, expected_names)
            source = SourceIdentity(source_id=model_source_name(bundle.model_id), model_id=bundle.model_id)
            layout = channel.tensor_layout(entity_ids=expected_names, source_identity=source)
            values = np.frombuffer(channel.data, dtype=layout.dtype).reshape(layout.shape)
            layout.validate_array(values)
            self.assertTrue(np.isfinite(values).any())
            # A missing declared joint keeps its authored positions without shifting later angles.
            reconstruction = output.reconstructions[STANDARD_HUMAN_MODEL_ID]
            omitted_name = next(iter(reconstruction.joint_angles))
            remaining = {name: angles for name, angles in reconstruction.joint_angles.items() if name != omitted_name}
            changed = replace(output, reconstructions={**output.reconstructions,
                STANDARD_HUMAN_MODEL_ID: replace(reconstruction, joint_angles=remaining)})
            unavailable, = producer.fill(replace(frame_context, aggregator_output=changed), bundle)
            self.assertEqual(unavailable.names, expected_names)
            missing_values = np.frombuffer(unavailable.data, dtype=layout.dtype).reshape(layout.shape)
            selection = layout.prepare_selection("entity_identity", tuple(bundle.skeleton.joints[omitted_name].angle_names))
            self.assertTrue(np.isnan(selection.select_values(missing_values, source_layout=layout)).all())
        finally:
            try:
                manager.shutdown()
            finally:
                try:
                    service.close()
                finally:
                    try:
                        registry.shutdown_all()
                    finally:
                        if capture is not None:
                            capture.close_transport()
                        if group is not None:
                            group.close()
            self.assertFalse(registry.alive_workers, "Realtime workers survived shutdown")
            for name in memory_names:
                try:
                    leaked = shared_memory.SharedMemory(name=name)
                except FileNotFoundError:
                    continue
                leaked.close()
                self.fail(f"Shared memory survived shutdown: {name}")
            self.assertEqual(file_digest(structure.data_parquet_path), original_digest)
