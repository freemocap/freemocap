from freemocap.core.pipeline.inference_service import InferenceService
import unittest
import multiprocessing
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from unittest.mock import Mock

from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage


class TerminalProgressTests(unittest.TestCase):
    def test_evicted_failure_remains_available_to_multiple_clients(self) -> None:
        manager = PosthocPipelineManager(inference_service=Mock(spec=InferenceService), global_kill_flag=multiprocessing.Value('b', False), worker_registry=Mock(spec=WorkerRegistry))
        failure = AggregatorNodeProgressMessage(
            pipeline_id="calibration-task", phase=AggregatorPhase.FAILED,
            detail="No usable board observations", pipeline_type="calibration",
        )
        pipeline = Mock(started=True, alive=False)
        pipeline.drain_and_get_messages.return_value = [failure]
        manager.pipelines[failure.pipeline_id] = pipeline
        manager.evict_completed()
        self.assertFalse(manager.pipelines)
        for _ in range(3):
            self.assertEqual(manager.get_progress_updates(), [failure])
        pipeline.shutdown.assert_called_once()

    def test_terminal_history_is_bounded(self) -> None:
        manager = PosthocPipelineManager(inference_service=Mock(spec=InferenceService), global_kill_flag=multiprocessing.Value('b', False), worker_registry=Mock(spec=WorkerRegistry))
        manager._retain_terminal_progress([
            AggregatorNodeProgressMessage(pipeline_id=str(index), phase=AggregatorPhase.COMPLETE)
            for index in range(105)
        ])
        self.assertEqual(len(manager.terminal_progress), 100)
        self.assertNotIn("0", manager.terminal_progress)
        self.assertIn("104", manager.terminal_progress)
