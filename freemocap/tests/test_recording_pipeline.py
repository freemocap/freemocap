"""Real checkpoint persistence under failed reconstruction and strict graph bindings."""
from freemocap.tests import test_dataflow_scientific_recording as fixtures
from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
from freemocap.core.pipeline.dataflow.recording_pipeline import build_recording_pipeline
from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
from freemocap.core.pipeline.dataflow.definition import compile_graph, PortReference
from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.types.channel_kind import ChannelKind
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition
from skellycam.core.recorders.videos.recording_info import RecordingInfo
import unittest
from dataclasses import replace
import cv2
import numpy as np
from freemocap.core.pipeline.dataflow.camera_join import ProducerOutcome


class RecordingPipelineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ScientificRecordingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        source = self.fixture
        self.calibration = source.root / "calibration.toml"
        CalibrationResult(cameras=list(source.cameras), board=CharucoBoardDefinition.create_letter_size_5x3(),
            reprojection_error_px=0., initial_cost=0., final_cost=0., n_iterations=1,
            time_seconds=0., n_observations_used=360, n_observations_rejected=0).save_toml(self.calibration)

    def graph(self, *, observation_override=None, **options):
        source = self.fixture
        observations = ObservationCollection(sources=source.sources, execution_id="run")
        for event in source.events + source.outcomes:
            observations.accept(event)
        config = PosthocMocapPipelineConfig(charuco_tracking_enabled=False, export_to_blender=False,
            calibration_toml_path=str(self.calibration), body_alignment=MocapAlignmentConfig(mode="calibration"))
        return build_recording_pipeline(sources=source.sources,
            recording=RecordingInfo(recording_name=source.root.name, recording_directory=str(source.root.parent)),
            config=config, observation_loader=lambda: observation_override or observations, **options)

    def test_failed_reconstruction_preserves_completed_checkpoints_and_annotations(self):
        graph, handlers = self.graph(annotate=True)
        original_science = handlers["match_and_triangulate"]
        def continued_warning(inputs):
            from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingStatus
            output = original_science(inputs)
            science = output["result"]
            return {"result": replace(science, matching_result=replace(science.matching_result, status=CameraMatchingStatus.POOR))}
        handlers["match_and_triangulate"] = continued_warning
        def fail(_):
            raise ValueError("Injected reconstruction failure")
        handlers["reconstruct_skeletons"] = fail
        for index in range(3):
            handlers[f"annotate_camera_{index}"] = lambda inputs: {"result": "independent annotation completed"}
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertIn("reconstruct_skeletons", result.failures)
        self.assertIn("save_recording", result.blocked)
        self.assertIn("save_observations", result.outputs)
        self.assertIn("save_spatial", result.outputs, result.failures)
        for index in range(3):
            self.assertIn(f"annotate_camera_{index}", result.outputs)
        source = self.fixture
        metadata = read_metadata(path=RecordingStructure(base_directory=source.root.parent, recording_name=source.root.name).data_parquet_path)
        kinds = {channel.kind for channel in metadata.runs[0].channels}
        self.assertIn(ChannelKind.RAW_KEYPOINTS_3D, kinds)
        self.assertNotIn(ChannelKind.LANDMARKS_3D, kinds)
        assignment = metadata.runs[0].processing[source.sources.sensor_group]["camera_assignment"]
        self.assertIn("fitness", assignment)
        self.assertIn("source_to_calibration", assignment)
        self.assertEqual(assignment["status"], "poor")
        self.assertEqual(assignment["error_units"], "pixels_at_1000_pixel_image_diagonal")
        self.assertEqual(len(assignment["fitness"]["cameras"]), 3)
        from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
        from unittest.mock import patch
        # Reusing saved 2D data must not regenerate discarded observation batches.
        with patch("freemocap.core.recording.result_processing.observation_publication.observation_batches",
                   side_effect=AssertionError("Rebuilt reused observations")):
            publish_posthoc_observations(result.outputs["spatial_request"]["result"])
        saved_again = read_metadata(path=RecordingStructure(base_directory=source.root.parent, recording_name=source.root.name).data_parquet_path)
        self.assertEqual(assignment, saved_again.runs[0].processing[source.sources.sensor_group]["camera_assignment"])

    def test_wrong_producer_cannot_redefine_consumer_contract(self):
        graph, _ = self.graph()
        edges = tuple(edge.model_copy(update={"source": PortReference(node="filter_trajectories", port="result")})
                      if edge.target.node == "observation_request" else edge for edge in graph.definition.edges)
        with self.assertRaisesRegex(ValueError, "Incompatible data semantics"):
            compile_graph(graph.definition.model_copy(update={"edges": edges}))

    def test_failed_camera_keeps_other_camera_annotation_outputs(self):
        source = self.fixture
        collection = ObservationCollection(sources=source.sources, execution_id="run")
        collection.accept(replace(source.outcomes[0], outcome=ProducerOutcome.FAILED, loaded_frames=0))
        for event in source.events:
            if event.frame_key.camera != "camera0":
                collection.accept(event)
        for outcome in source.outcomes[1:]:
            collection.accept(outcome)
        for camera in source.sources.camera_sources[1:]:
            writer = cv2.VideoWriter(str(camera.video_metadata.file_path), cv2.VideoWriter_fourcc(*"mp4v"), 30., (1280, 720))
            self.assertTrue(writer.isOpened())
            try:
                for _ in range(12):
                    writer.write(np.zeros((720, 1280, 3), dtype=np.uint8))
            finally:
                writer.release()
        graph, handlers = self.graph(observation_override=collection, annotate=True)
        result = execute_recording_graph(graph=graph, handlers=handlers)
        self.assertIn("match_and_triangulate", result.failures)
        self.assertIn("annotate_camera_0", result.failures)
        for index in (1, 2):
            self.assertIn(f"annotate_camera_{index}", result.outputs, result.failures)
            self.assertTrue(result.outputs[f"annotate_camera_{index}"]["result"].is_file())
        self.assertNotIn("save_recording", result.outputs)
