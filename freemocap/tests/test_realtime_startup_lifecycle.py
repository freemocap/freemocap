"""Delayed native facades exercise API-loop responsiveness and cleanup ownership."""

import asyncio
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.app.freemocap_application import (
    FreemocapApplication, RealtimeStartupConfigurationError, RealtimeStartupStopped,
)
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus


def application():
    app = object.__new__(FreemocapApplication)
    app.global_kill_flag = SimpleNamespace(value=False)
    app.startup_status = RealtimeStartupStatus()
    app._realtime_lifecycle_lock = asyncio.Lock()
    app._realtime_startup_operation = None
    app._realtime_stop_task = None
    app._startup_pipeline_owned = False
    app.realtime_pipeline_manager = Mock(spec=RealtimePipelineManager)
    app.realtime_pipeline_manager.pipelines = {}
    app.camera_group_manager = SimpleNamespace(
        backend="python", create_or_update_camera_group=AsyncMock(return_value=object()),
    )
    return app


def pipeline():
    result = Mock(spec=RealtimePipeline)
    result.id = "pipeline"
    result.alive = True
    result.camera_ids = ["camera"]
    result.get_latest_aggregator_output.return_value = None
    return result


async def apply(app):
    return await app.create_or_update_realtime_pipeline(camera_configs={}, pipeline_config=RealtimePipelineConfig())


async def test_legacy_tensorrt_rejected_before_cameras_or_pipeline_mutation():
    app = application()
    config = RealtimePipelineConfig(use_centralized_inference=False)
    config.skeleton_inference_node_config.execution_provider = 'trt'
    with pytest.raises(RealtimeStartupConfigurationError, match='requires centralized realtime inference'):
        await app.create_or_update_realtime_pipeline(camera_configs={}, pipeline_config=config)
    app.camera_group_manager.create_or_update_camera_group.assert_not_awaited()
    app.realtime_pipeline_manager.create_pipeline.assert_not_called()
    app.realtime_pipeline_manager.update_pipeline_config.assert_not_called()
    assert app.startup_status.snapshot()['status'] == 'failed'


async def test_new_pipeline_start_is_off_loop_and_waits_for_frames():
    app = application()
    capture = Mock(spec=CaptureGroup)
    created = pipeline()
    entered, release = Event(), Event()
    worker_ids = []

    def create(**kwargs):
        worker_ids.append(get_ident())
        entered.set()
        assert release.wait(3)
        app.realtime_pipeline_manager.pipelines[created.id] = created
        return created

    app.realtime_pipeline_manager.create_pipeline.side_effect = create
    with patch("freemocap.app.freemocap_application.CaptureGroup", return_value=capture):
        task = asyncio.create_task(apply(app))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
            assert app.startup_status.snapshot()["phase"] == "starting_pipeline"
            assert not task.done()
            assert worker_ids[0] != get_ident()
        finally:
            release.set()
        assert await task is created
    state = app.startup_status.snapshot()
    assert state["status"] == "running" and state["phase"] == "waiting_for_frames"
    assert state["pipeline_id"] == created.id
    capture.close_transport.assert_not_called()


@pytest.mark.parametrize("cancel_caller", [False, True])
async def test_stopping_blocked_creation_waits_for_real_completion_and_cleans_new_pipeline(cancel_caller):
    app = application()
    created = pipeline()
    entered, release = Event(), Event()

    def create(**kwargs):
        entered.set()
        assert release.wait(3)
        app.realtime_pipeline_manager.pipelines[created.id] = created
        return created

    app.realtime_pipeline_manager.create_pipeline.side_effect = create
    with patch("freemocap.app.freemocap_application.CaptureGroup", return_value=Mock(spec=CaptureGroup)):
        task = asyncio.create_task(apply(app))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            if cancel_caller:
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
            else:
                assert await app.stop_realtime_startup()
            assert app.startup_status.snapshot()["status"] == "stopping"
            assert not task.done()
            assert app._realtime_lifecycle_lock.locked()
            app.realtime_pipeline_manager.stop_pipeline.assert_not_called()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError if cancel_caller else RealtimeStartupStopped):
            await task
    app.realtime_pipeline_manager.stop_pipeline.assert_called_once_with(pipeline_id=created.id)
    assert app.startup_status.snapshot()["status"] == "stopped"
    assert not app._realtime_lifecycle_lock.locked()


async def test_stop_during_camera_start_does_not_build_pipeline_or_claim_native_cancel():
    app = application()
    entered, release = asyncio.Event(), asyncio.Event()

    async def cameras(**kwargs):
        entered.set()
        await release.wait()
        return object()

    app.camera_group_manager.create_or_update_camera_group.side_effect = cameras
    task = asyncio.create_task(apply(app))
    await entered.wait()
    assert await app.stop_realtime_startup()
    assert not task.done()
    assert app.startup_status.snapshot()["phase"] == "starting_cameras"
    release.set()
    with pytest.raises(RealtimeStartupStopped):
        await task
    app.realtime_pipeline_manager.create_pipeline.assert_not_called()
    assert app.startup_status.snapshot()["status"] == "stopped"


async def test_stop_during_existing_update_preserves_existing_pipeline():
    app = application()
    existing = pipeline()
    app.realtime_pipeline_manager.pipelines[existing.id] = existing
    entered, release = Event(), Event()

    def update(**kwargs):
        entered.set()
        assert release.wait(3)
        return existing

    app.realtime_pipeline_manager.update_pipeline_config.side_effect = update
    task = asyncio.create_task(apply(app))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert await app.stop_realtime_startup()
        assert app.startup_status.snapshot()["phase"] == "updating_pipeline"
    finally:
        release.set()
    with pytest.raises(RealtimeStartupStopped):
        await task
    app.realtime_pipeline_manager.stop_pipeline.assert_not_called()
    app.camera_group_manager.create_or_update_camera_group.assert_not_called()


async def test_stop_after_creation_before_first_frame_schedules_owned_cleanup():
    app = application()
    created = pipeline()
    app.realtime_pipeline_manager.create_pipeline.return_value = created
    with patch("freemocap.app.freemocap_application.CaptureGroup", return_value=Mock(spec=CaptureGroup)):
        await apply(app)
    assert await app.stop_realtime_startup()
    assert app.startup_status.snapshot()["status"] == "stopping"
    await app._realtime_stop_task
    app.realtime_pipeline_manager.stop_pipeline.assert_called_once_with(pipeline_id=created.id)
    assert app.startup_status.snapshot()["status"] == "stopped"


async def test_failure_closes_owned_transport_and_retry_resets_error():
    app = application()
    capture = Mock(spec=CaptureGroup)
    app.realtime_pipeline_manager.create_pipeline.side_effect = RuntimeError("startup failed")
    with patch("freemocap.app.freemocap_application.CaptureGroup", return_value=capture):
        with pytest.raises(RuntimeError, match="startup failed"):
            await apply(app)
        capture.close_transport.assert_called_once()
        assert app.startup_status.snapshot()["error"] == "startup failed"
        app.realtime_pipeline_manager.create_pipeline.side_effect = None
        app.realtime_pipeline_manager.create_pipeline.return_value = pipeline()
        await apply(app)
    assert app.startup_status.snapshot()["error"] is None
    assert app.startup_status.snapshot()["phase"] == "waiting_for_frames"


async def test_manager_map_readers_do_not_wait_for_startup_or_update():
    manager = RealtimePipelineManager(worker_registry=Mock(spec=WorkerRegistry), inference_service=Mock(spec=InferenceService))
    created = pipeline()
    capture = Mock(spec=CaptureGroup)
    capture.camera_ids = ["camera"]
    capture.id = "group"
    entered, release = Event(), Event()

    def blocked():
        entered.set()
        assert release.wait(3)

    created.start.side_effect = blocked
    with patch("freemocap.core.pipeline.realtime.realtime_pipeline_manager.RealtimePipeline.create", return_value=created):
        task = asyncio.create_task(asyncio.to_thread(manager.create_pipeline, camera_group=capture,
                                                      pipeline_config=RealtimePipelineConfig()))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert manager.get_latest_aggregator_outputs(if_newer_than=-1) == []
            await asyncio.wait_for(manager.wait_for_any_result_ready(timeout=0.0), timeout=0.2)
            assert not task.done()
        finally:
            release.set()
        assert await task is created
    entered.clear()
    release.clear()
    created.update_config.side_effect = lambda **kwargs: blocked()
    task = asyncio.create_task(asyncio.to_thread(manager.update_pipeline_config,
                                                 pipeline_id=created.id, new_config=RealtimePipelineConfig()))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        assert manager.get_latest_aggregator_outputs(if_newer_than=-1) == []
        assert manager.get_pipeline_by_camera_ids(["camera"]) is created
    finally:
        release.set()
    assert await task is created


def test_failed_shutdown_keeps_pipeline_owned_for_retry():
    manager = RealtimePipelineManager(worker_registry=Mock(spec=WorkerRegistry), inference_service=Mock(spec=InferenceService))
    existing = pipeline()
    manager.pipelines[existing.id] = existing
    existing.shutdown.side_effect = RuntimeError("native worker did not stop")
    with pytest.raises(RuntimeError, match="did not stop"):
        manager.stop_pipeline(pipeline_id=existing.id)
    assert manager.pipelines[existing.id] is existing
    existing.shutdown.side_effect = None
    assert manager.stop_pipeline(pipeline_id=existing.id)
    assert manager.pipelines == {}


def test_status_has_terminal_elapsed_time_and_cannot_claim_ready_while_stopping():
    status = RealtimeStartupStatus()
    assert not status.request_stop()
    status.begin()
    status.phase("starting_cameras")
    assert status.request_stop()
    status.ready()
    assert status.snapshot()["status"] == "stopping"
    status.stopped()
    first = status.snapshot()
    assert status.snapshot()["elapsed_seconds"] == first["elapsed_seconds"]
    assert not status.request_stop()


def test_only_matching_delivered_frame_can_mark_ready():
    status = RealtimeStartupStatus()
    status.begin()
    status.pipeline_created("new")
    status.record_frame_delivery("old")
    assert status.snapshot()["phase"] == "waiting_for_frames"
    status.record_frame_delivery("new")
    assert status.snapshot()["status"] == "ready"
    terminal = status.snapshot()["elapsed_seconds"]
    status.record_frame_delivery("new")
    assert status.snapshot()["elapsed_seconds"] == terminal
    status.begin()
    status.pipeline_created("new")
    status.request_stop()
    status.record_frame_delivery("new")
    assert status.snapshot()["status"] == "stopping"
