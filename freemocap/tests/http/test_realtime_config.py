"""Client restoration reads server configuration without updating the pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.realtime.realtime_router import realtime_router
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig


def test_running_config_is_read_only_and_preserves_explicit_selection() -> None:
    config = RealtimePipelineConfig()
    config.aggregator_config.calibration_toml_path = 'C:/selected.toml'
    pipeline = SimpleNamespace(alive=True, config=config, update_config=Mock())
    pipelines = {'live': pipeline}
    application = SimpleNamespace(realtime_pipeline_manager=SimpleNamespace(pipelines=pipelines))
    app = FastAPI()
    app.include_router(realtime_router)
    with patch('freemocap.api.http.realtime.realtime_router.get_freemocap_app', return_value=application):
        with TestClient(app) as client:
            for _ in range(2):
                response = client.get('/realtime/config')
                assert response.status_code == 200
                assert response.json() == config.model_dump(mode='json')
            pipeline.update_config.assert_not_called()
            pipelines.clear()
            assert client.get('/realtime/config').json() is None
