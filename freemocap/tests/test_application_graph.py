"""Application graph routing and export ownership regression checks."""
from concurrent.futures import CancelledError
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from freemocap.core.pipeline.inference_service import InferenceService
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import multiprocessing

from freemocap.core.pipeline.dataflow.application_pipeline import validate_application_graph, run_application_graph
from freemocap.core.pipeline.dataflow.recording_executor import RecordingExecutionResult
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapWorkerRequest, _run_mocap_pipeline
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from skellycam.core.recorders.videos.recording_info import RecordingInfo

class ApplicationGraphTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.calibration=self.root/'selected.toml'; self.calibration.write_text('test calibration')
        self.config=PosthocMocapPipelineConfig(pipeline_implementation='typed_dataflow',
            charuco_tracking_enabled=False, graph_execution_provider='cpu',
            calibration_toml_path=str(self.calibration), export_to_blender=False)

    def test_current_pipeline_remains_default(self):
        self.assertEqual(PosthocMocapPipelineConfig().pipeline_implementation,'current')

    def test_saved_stage_is_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError,'starts at 2D tracking'):
            validate_application_graph(config=self.config.model_copy(update={'start_stage':'reconstruction'}))

    def test_worker_routes_to_graph(self):
        request=Mock(spec=MocapWorkerRequest,config=self.config)
        with patch('freemocap.core.pipeline.dataflow.application_pipeline.run_application_graph') as run:
            _run_mocap_pipeline(request=request)
            run.assert_called_once_with(request=request)

    def test_graph_exports_run_once_and_calibration_stays_local(self):
        from queue import Queue
        destination=self.root/'recording'; destination.mkdir()
        request=MocapWorkerRequest(pipeline_id='test',recording=RecordingInfo(recording_name='recording',recording_directory=str(self.root)),
            config=self.config,ipc=Mock(spec=PipelineIPC,should_continue=True,pipeline_shutdown_flag=multiprocessing.Value('b',False)),
            progress_queue=Queue(),registry=Mock(spec=WorkerRegistry),inference_service=Mock(spec=InferenceService),video_nodes=[])
        sources=SimpleNamespace(recording_path=destination,camera_sources=[])
        with patch('freemocap.core.pipeline.dataflow.application_pipeline.RecordingVideoSources.resolve',return_value=sources), \
             patch('freemocap.core.pipeline.dataflow.application_pipeline.run_recording_pipeline',return_value=RecordingExecutionResult()) as run, \
             patch('freemocap.core.pipeline.posthoc.mocap_pipeline.complete_mocap') as complete:
            run_application_graph(request=request)
            complete.assert_called_once()
            self.assertFalse(run.call_args.kwargs['config'].scientific_exports.formats)
            self.assertFalse(run.call_args.kwargs['config'].export_to_blender)
            self.assertTrue(Path(run.call_args.kwargs['config'].calibration_toml_path).is_relative_to(destination))
            self.assertEqual(self.calibration.read_text(),'test calibration')
            first_copy = Path(run.call_args.kwargs['config'].calibration_toml_path)
            first_copy.write_text('aligned geometry from the previous run')
            run_application_graph(request=request)
            second_copy = Path(run.call_args.kwargs['config'].calibration_toml_path)
            self.assertNotEqual(first_copy, second_copy)
            self.assertEqual(second_copy.read_text(), 'test calibration')

    def test_failed_or_cancelled_graph_never_reports_complete(self):
        from queue import Queue
        destination=self.root/'recording';destination.mkdir()
        request=MocapWorkerRequest(pipeline_id='test',recording=RecordingInfo(recording_name='recording',recording_directory=str(self.root)),
            config=self.config,ipc=Mock(spec=PipelineIPC,should_continue=True,pipeline_shutdown_flag=multiprocessing.Value('b',False)),
            progress_queue=Queue(),registry=Mock(spec=WorkerRegistry),inference_service=Mock(spec=InferenceService),video_nodes=[])
        for result,exception in [(RecordingExecutionResult(cancelled=True),CancelledError),
                                 (RecordingExecutionResult(failures={'science':'failed'}),RuntimeError)]:
            with patch('freemocap.core.pipeline.dataflow.application_pipeline.RecordingVideoSources.resolve',return_value=SimpleNamespace(recording_path=destination)), \
                 patch('freemocap.core.pipeline.dataflow.application_pipeline.run_recording_pipeline',return_value=result), \
                 patch('freemocap.core.pipeline.posthoc.mocap_pipeline.complete_mocap') as complete:
                with self.assertRaises(exception):run_application_graph(request=request)
                complete.assert_not_called()
