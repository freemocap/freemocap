"""Processing cannot start until revoked playback responses close their files."""

import asyncio
import multiprocessing
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import Mock

import anyio
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import FileResponse, StreamingResponse
from starlette.types import Message
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.api.http.playback.recording_access import RecordingPlaybackRoute
from freemocap.api.http.playback.playback_router import playback_router
from freemocap.core.recording.recording_access import (
    RecordingAccess,
    RecordingBusyError,
)
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import (
    PosthocPipelineManager,
)
from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType


def test_reservation_waits_for_actual_release_and_isolates_recordings(
    tmp_path: Path,
) -> None:
    access = RecordingAccess()
    recording = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    cancelled: list[bool] = []
    with access.read(
        path=recording.full_path / "video.mp4", cancel=lambda: cancelled.append(True)
    ):
        access.reserve(recording=recording, task_id="task")
        assert cancelled == [True]
        assert not access.ready(task_id="task")
        with pytest.raises(RecordingBusyError):
            with access.read(path=recording.full_path, cancel=lambda: None):
                pytest.fail("A reserved recording admitted a reader")
        with access.read(path=tmp_path / "other", cancel=lambda: None):
            pass
        with pytest.raises(RecordingBusyError):
            access.reserve(recording=recording, task_id="second")
    assert access.ready(task_id="task")
    access.release(task_id="task")
    assert access.snapshot() == ()


def test_busy_recording_blocks_content_and_absolute_file_route(tmp_path: Path) -> None:
    access = RecordingAccess()
    recording = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    access.reserve(recording=recording, task_id="owner")
    app = FastAPI()
    app.state.recording_access = access
    app.include_router(playback_router)
    with TestClient(app) as client:
        bundle = client.get(
            "/playback/recording/bundle",
            params={"recording_parent_directory": str(tmp_path)},
        )
        download = client.get(
            "/playback/parquet", params={"path": str(recording.data_parquet_path)}
        )
        for response in (bundle, download):
            assert response.status_code == 409
            assert response.json()["owner"]["task_id"] == "owner"
        unrelated = client.get(
            "/playback/other/bundle",
            params={"recording_parent_directory": str(tmp_path)},
        )
        assert unrelated.status_code == 404


def test_manager_defers_start_and_retains_ownership_when_cleanup_fails(
    tmp_path: Path,
) -> None:
    manager = PosthocPipelineManager(
        global_kill_flag=multiprocessing.Value("b", False),
        worker_registry=Mock(spec=WorkerRegistry),
        inference_service=Mock(spec=InferenceService),
    )
    pipeline = Mock(spec=CalibrationPipeline)
    pipeline.id = "calibration"
    pipeline.pipeline_type = PosthocPipelineType.CALIBRATION
    pipeline.recording_info = RecordingInfo(
        recording_directory=str(tmp_path), recording_name="recording"
    )
    pipeline.started = False
    pipeline.alive = True
    pipeline.get_progress_messages.return_value = []
    with manager.access.read(path=tmp_path / "recording", cancel=lambda: None):
        manager._register(pipeline=pipeline)
        manager._start_ready(pipeline=pipeline)
        manager.refresh_progress()
        pipeline.start.assert_not_called()
        assert manager.task_snapshot().recording_owners[0].task_id == pipeline.id
    manager.refresh_progress()
    pipeline.start.assert_called_once()
    pipeline.shutdown.side_effect = RuntimeError("Reader still open")
    with pytest.raises(RuntimeError, match="Reader still open"):
        manager.stop_pipeline(
            pipeline_id=pipeline.id, pipeline_type=pipeline.pipeline_type
        )
    assert manager.access.snapshot()
    assert pipeline.id in manager.pipelines
    pipeline.shutdown.side_effect = None
    manager.stop_pipeline(pipeline_id=pipeline.id, pipeline_type=pipeline.pipeline_type)
    assert not manager.access.snapshot()


@pytest.mark.asyncio
@pytest.mark.parametrize("codec", [False, True])
async def test_response_revocation_closes_file_before_writer_admission(
    tmp_path: Path, codec: bool
) -> None:
    recording = RecordingStructure(base_directory=tmp_path, recording_name="recording")
    recording.full_path.mkdir()
    source = recording.full_path / "video.mp4"
    source.write_bytes(b"v" * 200_000)
    replacement = recording.full_path / "partial.mp4"
    replacement.write_bytes(b"replacement")
    access = RecordingAccess()
    api = FastAPI()
    api.state.recording_access = access
    router = APIRouter(route_class=RecordingPlaybackRoute)
    body_started = asyncio.Event()
    closed = asyncio.Event()

    @router.get("/{recording_id}/video", response_model=None)
    async def video(recording_id: str) -> FileResponse | StreamingResponse:
        if not codec:
            return FileResponse(source)

        async def chunks() -> AsyncIterator[bytes]:
            try:
                with source.open("rb") as stream:
                    yield stream.read(100)
                    await anyio.sleep_forever()
            finally:
                closed.set()

        return StreamingResponse(chunks())

    api.include_router(router)

    async def receive() -> Message:
        await anyio.sleep_forever()
        raise AssertionError("Unreachable")

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body":
            body_started.set()
            await anyio.sleep_forever()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/recording/video",
        "raw_path": b"/recording/video",
        "root_path": "",
        "query_string": f"recording_parent_directory={tmp_path.as_posix()}".encode(),
        "headers": [(b"range", b"bytes=0-150000")],
        "server": ("test", 80),
        "client": ("test", 1),
    }
    response = asyncio.create_task(api(scope, receive, send))
    await asyncio.wait_for(body_started.wait(), timeout=5)
    access.reserve(recording=recording, task_id="task")
    assert not access.ready(task_id="task")
    await asyncio.wait_for(response, timeout=5)
    assert access.ready(task_id="task")
    if codec:
        assert closed.is_set()
    replacement.replace(source)
    assert source.read_bytes() == b"replacement"
