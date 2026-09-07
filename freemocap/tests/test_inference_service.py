import multiprocessing
import unittest
from concurrent.futures import CancelledError
from threading import Event
from unittest.mock import Mock, patch

import numpy as np
from numpy.typing import NDArray
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.sessions.shared_sessions import SessionRequest, TrackerLease
from skellytracker.core.sessions.cpu_session import CpuSession, CpuSessionConfig
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.inference_service import (
    InferenceClient, InferenceMode, InferenceRegistration, InferenceRequest, InferenceService,
)


class InferenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.global_shutdown = multiprocessing.Value("b", False)
        self.registry = WorkerRegistry(global_kill_flag=self.global_shutdown, worker_mode=WorkerMode.THREAD)
        self.pool = Mock()
        self.leases: list[TrackerLease] = []
        self.pool.create_tracker.side_effect = self.create_lease
        self.patch = patch("freemocap.core.pipeline.inference_service.SharedSessionPool", return_value=self.pool)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.service = InferenceService(worker_registry=self.registry)
        self.service.start()
        self.addCleanup(self.service.close)

    def create_lease(self, *, config: TrackerConfig, requests: tuple[SessionRequest, ...]) -> TrackerLease:
        lease = Mock(spec=TrackerLease)
        lease.tracker = Mock()
        lease.tracker.process_batch.side_effect = self.infer
        self.leases.append(lease)
        return lease

    @staticmethod
    def infer(*, images: dict[str, NDArray[np.uint8]], frame_number: int, states: dict[str, TrackerState]) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
        return ({key: Observation(frame_number=frame_number, image_size=image.shape[:2], stages={})
                 for key, image in images.items()}, {key: TrackerState() for key in images})

    def client(self, *, name: str, mode: InferenceMode = InferenceMode.POSTHOC) -> InferenceClient:
        return self.service.register(InferenceRegistration(
            pipeline_id=name, mode=mode, tracker_config=TrackerConfig(stages=[]), sessions=(),
            shutdown_flag=multiprocessing.Value("b", False),
        ))

    @staticmethod
    def request(frame: int = 0) -> InferenceRequest:
        return InferenceRequest(frame_number=frame, images={"same-camera": np.zeros((8, 12, 3), dtype=np.uint8)})

    def test_source_names_do_not_share_temporal_state_between_clients(self) -> None:
        first = self.client(name="first")
        second = self.client(name="second")
        first.submit(self.request()).result(timeout=2)
        second.submit(self.request()).result(timeout=2)
        first.submit(self.request(frame=1)).result(timeout=2)
        self.assertEqual(self.leases[0].tracker.process_batch.call_args_list[0].kwargs["states"], {})
        self.assertEqual(self.leases[1].tracker.process_batch.call_args_list[0].kwargs["states"], {})
        self.assertIn("same-camera", self.leases[0].tracker.process_batch.call_args_list[1].kwargs["states"])

    def test_inference_failure_stops_only_its_client(self) -> None:
        first = self.client(name="failed")
        second = self.client(name="healthy")
        first.submit(self.request()).result(timeout=2)
        self.leases[0].tracker.process_batch.side_effect = ValueError("bad input")
        with self.assertRaisesRegex(ValueError, "bad input"):
            first.submit(self.request(frame=1)).result(timeout=2)
        second.submit(self.request()).result(timeout=2)
        self.assertTrue(first.registration.shutdown_flag.value)
        self.assertFalse(second.registration.shutdown_flag.value)
        self.assertFalse(self.global_shutdown.value)

    def test_submission_during_lease_retirement_does_not_sleep_with_work_ready(self) -> None:
        retiring = self.client(name="retiring")
        ready = self.client(name="ready", mode=InferenceMode.REALTIME)
        retiring.submit(self.request()).result(timeout=2)
        submitted, completed, slept_with_work = Event(), Event(), Event()
        original_wait = self.service._condition.wait

        def submit_during_close() -> None:
            future = ready.submit(self.request())
            future.add_done_callback(lambda result: completed.set())
            submitted.set()

        def observe_wait(timeout: float | None = None) -> bool:
            if ready._pending is not None:
                slept_with_work.set()
            return original_wait(timeout=timeout)

        self.leases[0].close.side_effect = submit_during_close
        with patch.object(self.service._condition, "wait", side_effect=observe_wait):
            retiring.close()
            self.assertTrue(submitted.wait(timeout=2))
            self.assertTrue(completed.wait(timeout=2))
        self.assertFalse(slept_with_work.is_set())
        self.assertIsNone(ready.failure)

    def test_active_cancellation_waits_for_native_work_and_discards_result(self) -> None:
        client = self.client(name="cancelled")
        client.submit(self.request()).result(timeout=2)
        entered, release = Event(), Event()

        def blocking_infer(**kwargs: object) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
            entered.set()
            if not release.wait(timeout=2):
                raise TimeoutError("Test inference was not released")
            return self.infer(**kwargs)

        self.leases[0].tracker.process_batch.side_effect = blocking_infer
        future = client.submit(self.request(frame=1))
        try:
            self.assertTrue(entered.wait(timeout=2))
            with self.assertRaisesRegex(RuntimeError, "outstanding"):
                client.submit(self.request(frame=2))
            client.close()
            self.assertFalse(future.done())
            self.leases[0].close.assert_not_called()
        finally:
            release.set()
        with self.assertRaises(CancelledError):
            future.result(timeout=2)

    def test_posthoc_rejects_skips_but_realtime_accepts_selected_ordinals(self) -> None:
        posthoc = self.client(name="recording")
        live = self.client(name="live", mode=InferenceMode.REALTIME)
        with self.assertRaisesRegex(ValueError, "consecutive"):
            posthoc.submit(self.request(frame=2))
        live.submit(self.request(frame=20)).result(timeout=2)
        live.submit(self.request(frame=25)).result(timeout=2)

    def test_ready_posthoc_is_scheduled_after_three_realtime_requests(self) -> None:
        entered, release = Event(), Event()
        blocker = self.client(name="blocker")
        blocker.submit(self.request()).result(timeout=2)

        def blocking_infer(**kwargs: object) -> tuple[dict[str, Observation], dict[str, TrackerState]]:
            entered.set()
            if not release.wait(timeout=2):
                raise TimeoutError("Test inference was not released")
            return self.infer(**kwargs)

        self.leases[0].tracker.process_batch.side_effect = blocking_infer
        active = blocker.submit(self.request(frame=1))
        self.assertTrue(entered.wait(timeout=2))
        completed: list[str] = []
        futures = []
        try:
            for index in range(4):
                name = f"live-{index}"
                future = self.client(name=name, mode=InferenceMode.REALTIME).submit(self.request())
                future.add_done_callback(lambda result, label=name: completed.append(label))
                futures.append(future)
            future = self.client(name="posthoc").submit(self.request())
            future.add_done_callback(lambda result: completed.append("posthoc"))
            futures.append(future)
        finally:
            release.set()
        active.result(timeout=2)
        for future in futures:
            future.result(timeout=2)
        self.assertEqual(completed, ["live-0", "live-1", "live-2", "posthoc", "live-3"])


class InstalledSessionIntegrationTests(unittest.TestCase):
    def test_clients_use_installed_pool_and_survive_another_clients_release(self) -> None:
        global_shutdown = multiprocessing.Value("b", False)
        registry = WorkerRegistry(global_kill_flag=global_shutdown, worker_mode=WorkerMode.THREAD)
        service = InferenceService(worker_registry=registry)
        service.start()
        try:
            clients = [service.register(InferenceRegistration(
                pipeline_id=name, mode=InferenceMode.POSTHOC, tracker_config=TrackerConfig(stages=[]),
                sessions=(SessionRequest(session_type=CpuSession, config=CpuSessionConfig()),),
                shutdown_flag=multiprocessing.Value("b", False),
            )) for name in ("first", "second")]
            for client in clients:
                self.assertEqual(client.submit(InferenceServiceTests.request()).result(timeout=2)["same-camera"].frame_number, 0)
            self.assertIs(clients[0]._lease._entries[0].session, clients[1]._lease._entries[0].session)
            clients[0].close()
            self.assertEqual(clients[1].submit(InferenceServiceTests.request(frame=1)).result(timeout=2)["same-camera"].frame_number, 1)
            self.assertFalse(global_shutdown.value)
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()

