"""Invalid saved output must fail before mocap workers are created."""

from pathlib import Path
from multiprocessing.sharedctypes import Synchronized
from unittest.mock import Mock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry

from freemocap.api.http.playback.playback_router import playback_router
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.recording.sample_encoding.arrow_schema import DESCRIPTOR_KEY, SAMPLE_SCHEMA
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def test_invalid_metadata_blocks_workers_and_reports_file(tmp_path: Path) -> None:
    folder = tmp_path / "recording"
    folder.mkdir()
    path = folder / "recording_data.parquet"
    schema = SAMPLE_SCHEMA.with_metadata({DESCRIPTOR_KEY: b'{}'})
    pq.write_table(pa.Table.from_batches([], schema=schema), where=path)
    original = path.read_bytes()
    manager = PosthocPipelineManager(global_kill_flag=Mock(spec=Synchronized), worker_registry=Mock(spec=WorkerRegistry))
    with patch("freemocap.core.pipeline.posthoc.posthoc_pipeline_manager.PosthocPipeline.create") as create:
        with pytest.raises(ValueError, match="Recording metadata is incompatible or invalid"):
            manager.create_mocap_pipeline(
                recording_info=RecordingInfo(recording_directory=str(tmp_path), recording_name=folder.name, mic_device_index=-1),
                mocap_config=PosthocMocapPipelineConfig(),
            )
        create.assert_not_called()
    app = FastAPI()
    app.include_router(playback_router)
    with TestClient(app) as client:
        response = client.get("/playback/recording/manifest", params={"recording_parent_directory": str(tmp_path)})
        assert response.status_code == 422
        assert str(path) in response.json()["detail"]
    assert path.read_bytes() == original
