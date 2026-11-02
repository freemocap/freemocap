"""HTTP tests use real manager workers, but no camera/server/network emitter."""
from collections import deque
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from freemocap.api.http.streaming.streaming_router import get_streaming_outputs, streaming_router
from freemocap.core.streaming.message_model import FrameMessage
from freemocap.core.streaming.outputs.contracts import OutputSample, ProtocolDefinition, SourceBatch
from freemocap.core.streaming.outputs.manager import StreamingOutputManager


class Config(BaseModel):
    model_config = ConfigDict(extra='forbid')
    port: int = Field(default=39539, ge=1, le=65535)


class Source:
    ids = ()

    def __init__(self):
        self.pending = deque()

    def source_ids(self):
        return self.ids

    def poll(self):
        samples = tuple(self.pending)
        self.pending.clear()
        return SourceBatch(samples, self.ids)


class Emitter:
    def emit(self, sample):
        pass

    def close(self):
        pass


def test_vmc_quick_start_needs_no_body_and_reuses_only_active_defaults():
    from freemocap.core.streaming.outputs.vmc import VmcConfig

    source = Source()
    manager = StreamingOutputManager(source=source, protocols=(
        ProtocolDefinition('vmc', VmcConfig, lambda config: Emitter(), 'latest'),
    ))

    @asynccontextmanager
    async def lifespan(app):
        yield
        await manager.aclose()

    app = FastAPI(lifespan=lifespan)
    app.include_router(streaming_router, prefix='/freemocap')
    app.dependency_overrides[get_streaming_outputs] = lambda: manager
    base = '/freemocap/streaming'
    assert 'requestBody' not in app.openapi()['paths'][base + '/vmc/start']['post']
    with TestClient(app) as client:
        source.ids = ('a', 'b')
        assert client.post(base + '/vmc/start').status_code == 409
        source.ids = ()
        custom = client.post(base + '/outputs', json={'protocol': 'vmc', 'config': {'port': 39540}}).json()
        response = client.post(base + '/vmc/start')
        assert response.status_code == 200
        first = response.json()
        assert first['status'] == 'idle'
        assert first['pipeline_id'] is None
        assert first['config'] == VmcConfig().model_dump(mode='json')
        assert first['config']['profile'] == 'vrm0_normalized'
        schema = client.get(base + '/protocols').json()[0]['config_schema']
        assert schema['properties']['profile']['default'] == 'vrm0_normalized'
        assert schema['properties']['profile']['enum'] == ['vrm0_normalized', 'forge_reference_vrm_original']
        assert first['config']['host'] == '127.0.0.1' and first['config']['port'] == 39539
        assert first['id'] != custom['id']
        assert client.post(base + '/vmc/start').json()['id'] == first['id']
        assert len(manager.outputs) == 2
        client.delete(base + '/outputs/' + first['id'])
        restarted = client.post(base + '/vmc/start').json()
        assert restarted['id'] != first['id']
        assert client.get(base + '/outputs/' + custom['id']).json()['status'] == 'idle'


def test_output_http_observed_lifecycle_and_errors():
    source = Source()
    manager = StreamingOutputManager(source=source, protocols=(
        ProtocolDefinition('vmc', Config, lambda config: Emitter(), 'latest'),
        ProtocolDefinition('lsl', Config, lambda config: Emitter(), 'fail', lambda: 'missing test runtime'),
    ))

    @asynccontextmanager
    async def lifespan(app):
        yield
        await manager.aclose()

    app = FastAPI(lifespan=lifespan)
    app.include_router(streaming_router, prefix='/freemocap')
    app.dependency_overrides[get_streaming_outputs] = lambda: manager
    base = '/freemocap/streaming'
    with TestClient(app) as client:
        capabilities = client.get(base + '/protocols').json()
        assert capabilities[0]['config_schema']['properties']['port']['maximum'] == 65535
        assert capabilities[1]['available'] is False
        assert client.post(base + '/outputs', json={'protocol': 'missing'}).status_code == 404
        assert client.post(base + '/outputs', json={'protocol': 'vmc', 'config': {'port': 0}}).status_code == 422
        assert client.post(base + '/outputs', json={'protocol': 'lsl'}).status_code == 503
        assert client.get(base + '/outputs/missing').status_code == 404
        assert client.delete(base + '/outputs/missing').status_code == 404
        source.ids = ('a', 'b')
        assert client.post(base + '/outputs', json={'protocol': 'vmc'}).status_code == 409
        source.ids = ()
        created = client.post(base + '/outputs', json={'protocol': 'vmc', 'pipeline_id': 'a'})
        assert created.status_code == 201
        state = created.json()
        assert state['status'] == 'idle'
        assert source.ids == ()  # Creating an output never starts acquisition.
        url = base + '/outputs/' + state['id']
        second = client.post(base + '/outputs', json={'protocol': 'vmc', 'pipeline_id': 'b'}).json()
        source.ids = ('a',)
        source.pending.append(OutputSample(FrameMessage(frame_number=7), 'a', 9007199254740993))
        deadline = time.monotonic() + 2
        while (observed := client.get(url).json())['status'] != 'running':
            assert time.monotonic() < deadline
            time.sleep(.01)
        assert observed['frames_emitted'] == 1
        assert observed['last_capture_timestamp_ns'] == '9007199254740993'
        assert client.delete(url).json()['status'] == 'stopped'
        assert client.delete(url).json()['status'] == 'stopped'
        assert client.get(base + '/outputs/' + second['id']).json()['status'] == 'idle'
        assert len(client.get(base + '/outputs').json()) == 2
