"""DLC identity, rigid geometry, recording and self-describing transport integration."""
from dataclasses import replace
import json

import cbor2
import numpy as np
import pytest
import yaml

from freemocap.tests.test_dlc_application import dlc_sidecar
from freemocap.core.skeletons.dlc_object_skeleton import build_dlc_object_bundle
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel


@pytest.fixture
def object_inputs(dlc_sidecar):
    names = ('aft', 'bow', 'port', 'roof')
    points = np.array([[0., 0., 0.], [60., 0., 0.], [10., 25., 0.], [30., 10., 35.]])
    data = yaml.safe_load(dlc_sidecar.read_text())
    data['pose']['tracked_points'] = list(names)
    data['outputs'][0].update(shape=[-1, 4, 3], keypoint_count=4)
    dlc_sidecar.write_text(yaml.safe_dump(data))
    geometry = dlc_sidecar.parent / 'features.json'
    geometry.write_text(json.dumps(dict(schema_version=1, units='mm', feature_names=names,
        object_positions_mm=points.tolist(), reference_unit_mm=60., original_mesh_units='mm',
        source_mesh_to_object=[[1,0,0,-13],[0,1,0,7],[0,0,1,-2],[0,0,0,1]])))
    return dlc_sidecar, geometry, names, points


def test_object_identity_and_mesh_frame_survive_recording_roundtrip(object_inputs):
    sidecar, geometry, names, _ = object_inputs
    bundle = build_dlc_object_bundle(sidecar_path=sidecar, geometry_path=geometry)
    recorded = RecordedModel.from_bundle(bundle)
    restored = RecordedModel.model_validate_json(recorded.model_dump_json()).to_bundle()
    assert restored.object_geometry == bundle.object_geometry
    assert restored.tracker_keypoint_names == names
    assert restored.landmark_mapping.directly_measured_landmark_names == frozenset(names)
    matrices = bundle.object_geometry
    np.testing.assert_allclose(np.array(matrices.source_mesh_to_segment_reference).reshape(4,4)
        @ np.array(matrices.segment_reference_to_source_mesh).reshape(4,4), np.eye(4), atol=1e-12)
    data = json.loads(geometry.read_text())
    data['feature_names'].reverse()
    geometry.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='names and order'):
        build_dlc_object_bundle(sidecar_path=sidecar, geometry_path=geometry)


def test_object_live_reconstruction_publishes_one_tracker_and_mesh_frame(object_inputs):
    from freemocap.core.skeletons.reconstruction_state import build_reconstruction_states, streaming_model_scale_source
    from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
    from freemocap.core.streaming.message_composer import compose_messages
    from freemocap.core.streaming.producers.producer_contexts import StreamContext, FrameContext
    from freemocap.core.streaming.message_model import encode_message
    from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage
    from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
    from skellytracker.core.tracker.tracker_presets import dlc_tracker_metadata
    from skellyforge.core.data_tensors.channel_values import ChannelValues
    from skellytracker.core.data_primitives.observation import Observation, StageObservation
    from skellytracker.core.data_primitives.keypoints import Keypoints
    sidecar, geometry, names, points = object_inputs
    bundle = build_dlc_object_bundle(sidecar_path=sidecar, geometry_path=geometry)
    state = build_reconstruction_states(bundles=(bundle,), scale_source_for=streaming_model_scale_source(window_frames=8))[bundle.model_id]
    result = reconstruct_skeleton(bundle=bundle, state=state,
        filtered_keypoints=dict(zip(names, points + [20., 30., 2000.])), compute_center_of_mass=False)
    assert result.fitted_scale_mm == pytest.approx(60., abs=1e-6)
    cameras = ('left', 'right')
    observation = Observation(0, (480,640), {'dlc_keypoints': StageObservation('dlc_keypoints',
        keypoints=Keypoints(names, points, np.ones(4)))})
    composition = compose_messages(StreamContext(skeletons=(bundle,), independent_trackers=(dlc_tracker_metadata(sidecar_path=sidecar),),
        camera_ids=cameras, pipeline_live=True))
    aggregation = AggregationNodeOutputMessage(frame_number=0, pipeline_config=RealtimePipelineConfig(), camera_group_id='test',
        camera_node_outputs={c: CameraNodeOutputMessage(camera_id=c, frame_number=0, skeleton_observation=observation) for c in cameras},
        reconstructions={bundle.model_id: result},
        keypoints_arrays=ChannelValues.from_mapping(dict(zip(names, points + [20., 30., 2000.])), component_names=('x','y','z')))
    wire = cbor2.loads(encode_message(composition.compose_frame_message(FrameContext(0, 0., aggregator_output=aggregation))))
    assert len(wire['trackers']) == 1
    assert wire['models'][0]['object_geometry'] == bundle.object_geometry.model_dump(mode='json')
    assert wire['trackers'][0]['model_id'] == bundle.model_id
    overlays = [c for c in wire['trackers'][0]['channels'] if c['kind'] == 'OVERLAY_2D']
    assert len(overlays) == 2
    np.testing.assert_allclose(np.frombuffer(overlays[0]['data'], '<f4').reshape(4,3)[:,:2], points[:,:2])


def test_object_posthoc_graph_triangulates_fits_and_saves_without_human(object_inputs):
    from freemocap.tests.test_recording_pipeline import RecordingPipelineTests
    from freemocap.core.pipeline.dataflow.recording_processing import ObservationCollection
    from freemocap.core.pipeline.dataflow.recording_pipeline import build_recording_pipeline
    from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    from freemocap.core.tasks.triangulation.triangulator import Triangulator
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from skellytracker.core.data_primitives.observation import Observation, StageObservation
    from skellytracker.core.data_primitives.keypoints import Keypoints
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.system.recording_structure.recording_structure import RecordingStructure
    sidecar, geometry, names, points = object_inputs
    fixture = RecordingPipelineTests()
    fixture.setUp()
    source = fixture.fixture
    try:
        collection = ObservationCollection(sources=source.sources, execution_id='run')
        world = points + [20., 30., 2500.]
        pixels = Triangulator(cameras=list(source.cameras)).project(world)
        for event in source.events:
            xy = pixels[int(event.frame_key.camera[-1])]
            observation = Observation(event.observation.frame_number, event.observation.image_size,
                {'dlc_keypoints': StageObservation('dlc_keypoints', keypoints=Keypoints(names,
                    np.column_stack((xy, np.zeros(4))), np.ones(4)))})
            collection.accept(replace(event, observation=observation))
        for event in source.outcomes:
            collection.accept(event)
        config = PosthocMocapPipelineConfig(detectorType='dlc', dlcModelPath=str(sidecar), dlcGeometryPath=str(geometry),
            stopStage='reconstruction', graphExecutionProvider='cpu', charuco_tracking_enabled=False,
            export_to_blender=False, calibration_toml_path=str(fixture.calibration))
        graph, handlers = build_recording_pipeline(sources=source.sources,
            recording=RecordingInfo(recording_name=source.root.name, recording_directory=str(source.root.parent)),
            config=config, observation_loader=lambda: collection, execution_provider='cpu')
        assert 'reconstruct_skeletons' in handlers
        request = handlers['observation_request']({'observations': collection})['result']
        assert len(request.models) == 1
        assert request.models[0].object_geometry.feature_names == names
        result = execute_recording_graph(graph=graph, handlers=handlers)
        assert result.complete, result.failures
        structure = RecordingStructure(base_directory=source.root.parent, recording_name=source.root.name)
        saved = read_metadata(path=structure.data_parquet_path)
        assert request.models[0].model_id in saved.runs[0].models
        assert saved.runs[0].models[request.models[0].model_id].object_geometry == request.models[0].object_geometry
    finally:
        fixture.doCleanups()
