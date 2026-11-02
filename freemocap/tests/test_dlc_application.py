"""Generic DLC settings/API and observation-only persistence, without cameras or GPU."""
from dataclasses import replace
from unittest.mock import patch
import hashlib

import numpy as np
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from freemocap.api.http.dlc import dlc_router as routes
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.skeletons.tracked_skeleton_set import build_tracked_skeletons
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.tracker_factory import tracker_session_requests


@pytest.fixture
def dlc_sidecar(tmp_path):
    # Configuration-only tests: no inference claim for this deliberately small artifact.
    artifact = tmp_path / "pose_model.onnx"
    artifact.write_bytes(b"application-contract-fixture")
    data = dict(schema_version="v2024.09.1019", model_id="arbitrary_features",
        display_name="Arbitrary feature model", role=["pose_estimator"],
        input=dict(name="images", dtype={"fp32": "float32"}, layout="NCHW",
                   normalization="imagenet_rgb", resize={"method": "none"}),
        outputs=[dict(name="keypoints", dtype={"fp32": "float32"}, shape=[-1, 2, 3],
                      semantic="keypoints", fields=["x", "y", "confidence"], keypoint_axis=1, keypoint_count=2)],
        pose=dict(estimator_type="bottom_up", requires_object_detector=False,
                  tracked_points=["feature_z", "feature_a"], connections=[],
                  decode={"method": "coordinate", "coordinate_scale": "pixel"}),
        sizes={"native": {"input": {"shape": [-1, 3, 8, 12]}, "onnx": {"batch_artifacts": {
            "dynamic": {"precision_artifacts": {"fp32": {"filename": artifact.name,
                "url_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(), "cuda_use_tf32": False}}}}}}})
    sidecar = tmp_path / "arbitrary_features.yaml"
    sidecar.write_text(yaml.safe_dump(data), encoding="utf8")
    return sidecar


def test_dlc_settings_use_public_recipe_without_human_geometry(dlc_sidecar):
    camera = CameraNodeConfig(detector_type="dlc", dlc_model_path=str(dlc_sidecar),
                              dlc_confidence_threshold=.63, charuco_tracking_enabled=False)
    assert camera.skeleton_tracker_config.preset_name == "dlc"
    stage = camera.skeleton_tracker_config.stages[0]
    assert stage.name == "dlc_keypoints"
    assert stage.keypoint_detectors[0].confidence_threshold == .63
    with patch('freemocap.core.skeletons.tracked_skeleton_set.build_standard_human_bundle',
               side_effect=AssertionError("No anatomical model for arbitrary keypoints")):
        assert build_tracked_skeletons(camera_node_config=camera) == ()
    restored = CameraNodeConfig.model_validate_json(camera.model_dump_json(round_trip=True))
    assert restored.skeleton_settings == camera.skeleton_settings
    updated = camera.model_copy(update={"dlc_model_path": "different.yaml"})
    assert updated.skeleton_settings != camera.skeleton_settings
    requests = tracker_session_requests(config=camera.skeleton_tracker_config, batch_size=3, execution_provider="cpu")
    assert requests[0].config.fp16 is False
    assert requests[0].config.batch_size == 3
    assert requests[0].config.models[0].cuda_use_tf32 is False


@pytest.mark.parametrize("provider", [None, "trt", "coreml"])
def test_dlc_provider_contract_is_enforced(dlc_sidecar, provider):
    camera = CameraNodeConfig(detector_type="dlc", dlc_model_path=str(dlc_sidecar))
    with pytest.raises(ValueError, match="explicit CPU or CUDA"):
        tracker_session_requests(config=camera.skeleton_tracker_config, batch_size=1, execution_provider=provider)


def test_dlc_missing_selection_and_anatomical_processing_are_errors(dlc_sidecar):
    with pytest.raises(ValidationError, match="Select or import"):
        CameraNodeConfig(detector_type="dlc")
    camera = CameraNodeConfig(detector_type="dlc", dlc_model_path=str(dlc_sidecar))
    with pytest.raises(ValidationError, match="disable triangulation"):
        RealtimePipelineConfig(camera_node_config=camera, skeleton_inference_node_config={"execution_provider": "cpu"})
    config = RealtimePipelineConfig(camera_node_config=camera,
        skeleton_inference_node_config={"execution_provider": "cpu"},
        aggregator_config={"triangulation_enabled": False, "skeleton_fitting_enabled": False})
    assert config.camera_node_config.detector_type == "dlc"
    with pytest.raises(ValidationError, match="observation-only"):
        PosthocMocapPipelineConfig(detectorType="dlc", dlcModelPath=str(dlc_sidecar))


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(routes, "_jobs", {})
    app = FastAPI()
    app.include_router(routes.dlc_router, prefix="/freemocap")
    with TestClient(app) as client:
        yield client


def test_inspect_exposes_arbitrary_names_and_errors(api, dlc_sidecar):
    response = api.post('/freemocap/dlc/inspect', json={"sidecar_path": str(dlc_sidecar)})
    assert response.status_code == 200
    assert response.json()["keypoint_names"] == ["feature_z", "feature_a"]
    assert response.json()["precision"] == "fp32"
    assert response.json()["sidecar_path"] == str(dlc_sidecar.resolve())
    assert api.post('/freemocap/dlc/inspect', json={"sidecar_path": "absent.yaml"}).status_code == 422


def test_import_job_reports_completion_and_failure(api, dlc_sidecar, monkeypatch):
    monkeypatch.setattr(routes, 'dlc_conversion_readiness', lambda: {"available": True, "detail": "Ready"})
    monkeypatch.setattr(routes, 'convert_dlc_model', lambda request, output: dlc_sidecar)
    body = {"pose_config_path": "pose.yaml", "checkpoint_path": "snapshot.pt"}
    response = api.post('/freemocap/dlc/import', json=body)
    assert response.status_code == 202
    job = api.get('/freemocap/dlc/import/' + response.json()['job_id']).json()
    assert job['status'] == 'complete'
    assert job['result']['keypoint_names'] == ['feature_z', 'feature_a']
    def fail(*args):
        raise ValueError("Unsupported model backbone")
    monkeypatch.setattr(routes, 'convert_dlc_model', fail)
    response = api.post('/freemocap/dlc/import', json=body)
    job = api.get('/freemocap/dlc/import/' + response.json()['job_id']).json()
    assert job['status'] == 'failed'
    assert job['detail'] == 'Unsupported model backbone'
    assert api.get('/freemocap/dlc/import/unknown').status_code == 404


def test_missing_converter_is_reported_before_job_creation(api, monkeypatch):
    monkeypatch.setattr(routes, 'dlc_conversion_readiness', lambda: {"available": False, "detail": "Missing Torch/timm converter environment"})
    assert api.get('/freemocap/dlc/readiness').json()['available'] is False
    response = api.post('/freemocap/dlc/import', json={"pose_config_path": "pose.yaml", "checkpoint_path": "snapshot.pt"})
    assert response.status_code == 503
    assert 'converter environment' in response.json()['detail']
    assert routes._jobs == {}


def test_observation_graph_preserves_dlc_provenance_without_model(dlc_sidecar):
    from freemocap.tests.test_dataflow_scientific_recording import ScientificRecordingTests
    from freemocap.core.pipeline.dataflow.scientific_recording import ObservationCollection
    from freemocap.core.pipeline.dataflow.recording_pipeline import build_recording_pipeline
    from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellytracker.core.data_primitives.observation import Observation, StageObservation
    from skellytracker.core.data_primitives.keypoints import Keypoints
    fixture = ScientificRecordingTests()
    fixture.setUp()
    try:
        collection = ObservationCollection(sources=fixture.sources, execution_id="run")
        for event in fixture.events:
            observation = Observation(frame_number=event.observation.frame_number, image_size=(720, 1280),
                stages={"dlc_keypoints": StageObservation(name="dlc_keypoints", keypoints=Keypoints(
                    names=("feature_z", "feature_a"), xyz=np.array([[10., 20., 0.], [30., 40., 0.]]),
                    visibility=np.ones(2)))})
            collection.accept(replace(event, observation=observation))
        for event in fixture.outcomes:
            collection.accept(event)
        config = PosthocMocapPipelineConfig(detectorType="dlc", dlcModelPath=str(dlc_sidecar),
            stopStage="observations", graphExecutionProvider="cpu", charuco_tracking_enabled=False,
            export_to_blender=False)
        with patch('freemocap.core.pipeline.dataflow.recording_pipeline.build_standard_human_bundle',
                   side_effect=AssertionError("DLC must not construct a human")):
            graph, handlers = build_recording_pipeline(sources=fixture.sources,
                recording=RecordingInfo(recording_name=fixture.root.name, recording_directory=str(fixture.root.parent)),
                config=config, observation_loader=lambda: collection, execution_provider="cpu")
        assert 'reconstruct_skeletons' not in handlers
        request = handlers['observation_request']({'observations': collection})['result']
        assert request.models == ()
        assert request.detector is None
        assert request.tracker.name.startswith('keypoint_model:dlc:')
        assert request.tracker.configuration['dlc_model']['keypoint_names'] == ['feature_z', 'feature_a']
        result = execute_recording_graph(graph=graph, handlers=handlers)
        assert result.complete, result.failures
        structure = RecordingStructure(base_directory=fixture.root.parent, recording_name=fixture.root.name)
        metadata = read_metadata(path=structure.data_parquet_path)
        assert 'keypoint_model:dlc:' in metadata.model_dump_json()
        assert 'standard_human' not in metadata.model_dump_json()
    finally:
        fixture.doCleanups()
