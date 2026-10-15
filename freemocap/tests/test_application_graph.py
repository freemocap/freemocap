"""Application graph routing and export ownership regression checks."""
from concurrent.futures import CancelledError
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from freemocap.core.pipeline.inference_service import InferenceService
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
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

    def test_graph_is_default_and_legacy_remains_selectable(self):
        self.assertEqual(PosthocMocapPipelineConfig().pipeline_implementation,'typed_dataflow')
        self.assertEqual(PosthocMocapPipelineConfig(pipeline_implementation='current').pipeline_implementation, 'current')

    def test_saved_3d_starts_do_not_require_external_calibration(self):
        for start in ('filtering', 'scale_fit', 'reconstruction'):
            validate_application_graph(config=self.config.model_copy(update={'start_stage': start, 'calibration_toml_path': None}))

    def test_worker_routes_to_graph(self):
        request=Mock(spec=MocapWorkerRequest,config=self.config)
        with patch('freemocap.core.pipeline.dataflow.application_pipeline.run_application_graph') as run:
            _run_mocap_pipeline(request=request)
            run.assert_called_once_with(request=request)

    def test_graph_exports_run_once_and_reuses_unchanged_calibration(self):
        from queue import Queue
        destination=self.root/'recording'; destination.mkdir()
        request=MocapWorkerRequest(pipeline_id='test',recording=RecordingInfo(recording_name='recording',recording_directory=str(self.root)),
            config=self.config,ipc=Mock(spec=PipelineIPC,should_continue=True,pipeline_shutdown_flag=multiprocessing.Value('b',False)),
            progress_queue=Queue(),registry=Mock(spec=WorkerRegistry),inference_service=Mock(spec=InferenceService),video_nodes=[])
        sources=Mock(spec=RecordingVideoSources,recording_path=destination,camera_sources=[SimpleNamespace(video_metadata=SimpleNamespace(frame_count=222)) for _ in range(3)])
        with patch('freemocap.core.pipeline.dataflow.application_pipeline.RecordingVideoSources.resolve',return_value=sources), \
             patch('freemocap.core.pipeline.dataflow.application_pipeline.run_recording_pipeline',return_value=RecordingExecutionResult()) as run, \
             patch('freemocap.core.pipeline.posthoc.mocap_pipeline.complete_mocap') as complete:
            def execute(**kwargs):
                progress=kwargs['progress']
                progress('load_and_track','started',0.0)
                progress('load_and_track','tracking',0.5)
                progress('load_and_track','finished',1.0)
                progress('annotate_camera_0','started',0.0)
                progress('reconstruct_skeletons','started',0.0)
                return RecordingExecutionResult()
            run.side_effect=execute
            run_application_graph(request=request)
            messages=list(request.progress_queue.queue)
            detection=next(message for message in messages if '333' in message.detail)
            self.assertIn('3 videos x 222 frames each',detection.detail)
            self.assertIn('RTMPose on CPU',detection.detail)
            self.assertIn('percentage is for detection only',detection.detail)
            self.assertIn('annotated video 1',messages[-1].detail)
            self.assertIn('joint rotations',messages[-1].detail)
            self.assertIn('still processing',messages[-1].detail)
            operations = {operation.operation_id: operation for operation in messages[-1].operations}
            self.assertEqual(operations['load_and_track'].status, 'complete')
            self.assertEqual(operations['load_and_track'].completed, 666)
            self.assertEqual(operations['annotate_camera_0'].status, 'running')
            self.assertEqual(operations['reconstruct_skeletons'].status, 'running')
            complete.assert_called_once()
            self.assertFalse(run.call_args.kwargs['config'].scientific_exports.formats)
            self.assertFalse(run.call_args.kwargs['config'].export_to_blender)
            self.assertEqual(Path(run.call_args.kwargs['config'].calibration_toml_path), self.calibration)
            self.assertEqual(self.calibration.read_text(), 'test calibration')
            run_application_graph(request=request)
            self.assertEqual(Path(run.call_args.kwargs['config'].calibration_toml_path), self.calibration)
            self.assertFalse((destination / 'calibration_copies').exists())
            self.assertFalse((destination / 'exports' / 'calibration_copies').exists())

    def test_failed_or_cancelled_graph_never_reports_complete(self):
        from queue import Queue
        destination=self.root/'recording';destination.mkdir()
        request=MocapWorkerRequest(pipeline_id='test',recording=RecordingInfo(recording_name='recording',recording_directory=str(self.root)),
            config=self.config,ipc=Mock(spec=PipelineIPC,should_continue=True,pipeline_shutdown_flag=multiprocessing.Value('b',False)),
            progress_queue=Queue(),registry=Mock(spec=WorkerRegistry),inference_service=Mock(spec=InferenceService),video_nodes=[])
        for result,exception in [(RecordingExecutionResult(cancelled=True),CancelledError),
                                 (RecordingExecutionResult(failures={'science':'failed'}),RuntimeError)]:
            with patch('freemocap.core.pipeline.dataflow.application_pipeline.RecordingVideoSources.resolve',return_value=Mock(spec=RecordingVideoSources,recording_path=destination)), \
                 patch('freemocap.core.pipeline.dataflow.application_pipeline.run_recording_pipeline',return_value=result), \
                 patch('freemocap.core.pipeline.posthoc.mocap_pipeline.complete_mocap') as complete:
                with self.assertRaises(exception):run_application_graph(request=request)
                complete.assert_not_called()
