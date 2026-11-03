"""Preview and retained task plan contracts, independent of expensive inference."""
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch

from freemocap.core.pipeline.dataflow.processing_plan import build_processing_plan, preview_processing_plan, application_definition, plan_from_graph
from freemocap.core.pipeline.posthoc.operation_progress import OperationProgressReporter
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests import test_recording_pipeline as recording_fixtures


def test_preview_is_repeatable_and_does_not_allocate_or_load_models():
    fixture = recording_fixtures.RecordingPipelineTests(); fixture.setUp()
    try:
        path = fixture.fixture.root
        config = PosthocMocapPipelineConfig(calibration_toml_path=str(fixture.calibration),
            run_save_mode='new_run', export_to_blender=True)
        before = sorted(str(p.relative_to(path)) for p in path.rglob('*'))
        with patch('freemocap.core.pipeline.dataflow.video_sources.RecordingVideoSources.resolve', return_value=fixture.fixture.sources), \
             patch('freemocap.core.recording.result_processing.run_save_session.RunSaveSession.resolve', side_effect=AssertionError('allocated')), \
             patch('freemocap.core.tasks.calibration.shared.calibration_result.CalibrationResult.load_toml', side_effect=AssertionError('loaded calibration')):
            first = build_processing_plan(recording_path=path, config=config)
            second = build_processing_plan(recording_path=path, config=config)
        assert first == second
        assert before == sorted(str(p.relative_to(path)) for p in path.rglob('*'))
        assert first.graph.nodes[-1].id == 'blender'
        assert 'display' in first.graph.nodes[-1].effects
        changed = config.model_copy(update={'export_to_blender':False})
        assert plan_from_graph(graph=application_definition(config=changed,camera_count=3),config=changed,recording_path=path).plan_id != first.plan_id
    finally: fixture.doCleanups()


def test_invalid_preview_returns_errors_without_starting_work(tmp_path):
    result = preview_processing_plan(recording_path=tmp_path/'missing',config=PosthocMocapPipelineConfig())
    assert result.plan is None
    assert result.errors == ('Recording directory does not exist',)


def test_seeded_operations_remain_ordered_self_describing_and_track_dependencies(tmp_path):
    config = PosthocMocapPipelineConfig(export_to_blender=False,stop_stage='observations')
    plan = plan_from_graph(graph=application_definition(config=config,camera_count=2),config=config,recording_path=tmp_path)
    reporter = OperationProgressReporter()
    request = SimpleNamespace(pipeline_id='run',progress_queue=Queue(),recording=SimpleNamespace(recording_name='sample',full_recording_path=tmp_path/'sample'))
    reporter.initialize(request,plan)
    first = request.progress_queue.get()
    assert tuple(o.operation_id for o in first.operations) == plan.topological_order
    assert all(o.status == 'waiting' for o in first.operations)
    assert first.plan == plan
    assert reporter.operations['observation_request'].waiting_for == ('load_and_track',)
    reporter.update(request,'load_and_track','Read and track','running')
    reporter.artifacts(request,'load_and_track',reads=('camera.mp4',))
    reporter.update(request,'load_and_track','Read and track','complete')
    latest = list(request.progress_queue.queue)[-1]
    assert latest.plan == first.plan
    assert tuple(o.operation_id for o in latest.operations) == plan.topological_order
    assert reporter.operations['observation_request'].waiting_for == ()
    assert reporter.operations['load_and_track'].files_read == ('camera.mp4',)
    registry = TaskRegistry();registry.register(task_id='run',task_type='mocap',recording=RecordingStructure(base_directory=tmp_path,recording_name='sample'))
    registry.update(task_id='run',messages=[latest])
    assert registry.snapshot().tasks[0].plan == plan
    import cbor2
    from freemocap.core.streaming.message_model import ProgressMessage, encode_message
    from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistrySnapshot
    decoded = TaskRegistrySnapshot.model_validate(cbor2.loads(encode_message(
        ProgressMessage(snapshot=registry.snapshot())))["snapshot"])
    assert decoded.tasks[0].plan == plan
    assert decoded.tasks[0].operations == latest.operations



def test_http_preview_reports_validation_and_does_not_create_task(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from freemocap.api.http.recordings.processing_router import processing_router
    from freemocap.core.recording.recording_access import RecordingAccess
    (tmp_path/'clip').mkdir()
    app=FastAPI();app.state.recording_access=RecordingAccess();app.include_router(processing_router)
    with TestClient(app) as client:
        response=client.post('/recordings/clip/processing/plan',params={'recording_parent_directory':str(tmp_path)},json={'kind':'mocap','config':{}})
    assert response.status_code == 200, response.text
    assert response.json()['plan'] is None
    assert response.json()['errors'] == ['Typed data flow graph V1 requires an existing camera calibration file']
    assert not list((tmp_path/'clip').iterdir())
    assert not app.state.recording_access.readers


def test_saved_plan_uses_metadata_without_loading_arrays_or_allocating_run():
    from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
    fixture=recording_fixtures.RecordingPipelineTests();fixture.setUp()
    try:
        graph,handlers=fixture.graph(stop_stage='scale_fit')
        assert execute_recording_graph(graph=graph,handlers=handlers).complete
        path=fixture.fixture.root
        config=PosthocMocapPipelineConfig(start_stage='reconstruction',export_to_blender=False,run_save_mode='new_run')
        before=sorted(str(p.relative_to(path)) for p in path.rglob('*'))
        with patch('freemocap.core.pipeline.dataflow.video_sources.RecordingVideoSources.resolve',side_effect=AssertionError('opened videos')), \
             patch('freemocap.core.recording.result_processing.run_save_session.RunSaveSession.resolve',side_effect=AssertionError('allocated')), \
             patch('freemocap.core.recording.result_processing.saved_reconstruction.read_saved_channel',side_effect=AssertionError('loaded arrays')):
            plan=build_processing_plan(recording_path=path,config=config)
        assert 'load_saved_model_fits' in plan.topological_order
        assert before==sorted(str(p.relative_to(path)) for p in path.rglob('*'))
    finally:fixture.doCleanups()


def test_invalid_launch_does_not_allocate_ipc_or_worker(tmp_path):
    import pytest
    from unittest.mock import Mock
    from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
    from multiprocessing import Value
    from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
    from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
    workers = Mock(spec=WorkerRegistry)
    workers.heartbeat_timestamp = Value('d', 0.0)
    workers.create_worker.return_value = Mock(spec=ManagedWorker)
    with patch('freemocap.core.pipeline.posthoc.mocap_pipeline.PipelineIPC.create') as create_ipc:
        with pytest.raises(ValueError, match='Recording directory does not exist'):
            MocapPipeline.create(pipeline_id='invalid',
                recording_info=Mock(spec=RecordingInfo,full_recording_path=tmp_path/'missing'),
                config=PosthocMocapPipelineConfig(), worker_registry=workers, global_kill_flag=Value('b',False))
    create_ipc.assert_not_called()
    workers.create_worker.assert_not_called()


def test_created_pipeline_exposes_all_waiting_operations_before_worker_start(tmp_path):
    from unittest.mock import Mock
    from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
    config = PosthocMocapPipelineConfig(stop_stage='observations', export_to_blender=False)
    plan = plan_from_graph(graph=application_definition(config=config,camera_count=2),
        config=config,recording_path=tmp_path)
    from multiprocessing import Value
    from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
    from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
    from skellycam.core.recorders.videos.recording_info import RecordingInfo
    from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
    workers = Mock(spec=WorkerRegistry)
    workers.heartbeat_timestamp = Value('d', 0.0)
    workers.create_worker.return_value = Mock(spec=ManagedWorker)
    workers.create_worker.return_value.failure_exitcode = None
    with patch('freemocap.core.pipeline.dataflow.processing_plan.build_processing_plan',return_value=plan), \
         patch('freemocap.core.pipeline.posthoc.mocap_pipeline.PipelineIPC.create',return_value=Mock(spec=PipelineIPC,pipeline_shutdown_flag=Value('b',False),ws_queue=Mock())):
        pipeline = MocapPipeline.create(pipeline_id='queued',
            recording_info=Mock(spec=RecordingInfo,recording_name='sample',full_recording_path=tmp_path),
            config=config,worker_registry=workers,global_kill_flag=Value('b',False))
    message, = pipeline.get_progress_messages()
    assert message.plan == plan
    assert tuple(operation.operation_id for operation in message.operations) == plan.topological_order
    assert all(operation.status == 'waiting' for operation in message.operations)
    workers.create_worker.return_value.start.assert_not_called()


def test_preview_rejects_unsupported_provider_and_missing_source_run(tmp_path):
    config = PosthocMocapPipelineConfig(detector_type='mediapipe',graph_execution_provider='cuda',
        stop_stage='observations',export_to_blender=False)
    result = preview_processing_plan(recording_path=tmp_path,config=config)
    assert result.plan is None
    assert 'supports CPU only' in result.errors[0]
    config = PosthocMocapPipelineConfig(base_run_id=42,stop_stage='observations',export_to_blender=False)
    result = preview_processing_plan(recording_path=tmp_path,config=config)
    assert result.plan is None
    assert 'starts at Run 0' in result.errors[0]


def test_manifest_serialization_is_a_resource_constraint_not_a_data_edge(tmp_path):
    from freemocap.core.recording.exports.requests import ExportOptions
    config = PosthocMocapPipelineConfig(export_to_blender=False,export_tall_csv=True,
        export_options=ExportOptions(formats=['wide_csv']))
    graph = application_definition(config=config,camera_count=3)
    nodes = {node.id:node for node in graph.nodes}
    assert nodes['channel_exports'].execution_resource == nodes['tall_csv'].execution_resource == 'recording_export_manifest'
    assert not any(edge.source.node == 'channel_exports' and edge.target.node == 'tall_csv' for edge in graph.edges)
