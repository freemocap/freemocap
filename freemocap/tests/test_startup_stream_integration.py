"""Exercise startup HTTP, actual ASGI WebSocket bytes, and the installed TS decoder.

Uses a recorded synthetic image payload; never opens a camera or native detector.
"""

import asyncio
import base64
import json
from pathlib import Path
import shutil
import subprocess
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
import pytest
from skellytracker.core.data_primitives.observation import Observation

from freemocap.api.http.realtime import realtime_router as routes
from freemocap.api.websocket.frame_relay import FrameRelay
from freemocap.api.websocket.send_serializer import SendSerializer
from freemocap.api.websocket.websocket_server import WebsocketServer
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus
from freemocap.core.pipeline.realtime.realtime_pipeline_config import RealtimePipelineConfig
from freemocap.core.streaming.message_composer import compose_messages
from freemocap.core.streaming.producers.producer_contexts import FrameContext, StreamContext
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage, CameraNodeOutputMessage


def test_startup_remains_observable_until_frame_reaches_sdk_image_subscriber(monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    sdk = repo / "packages/freemocap-client"
    node = shutil.which("node")
    if node is None or not (sdk / "dist/index.js").is_file():
        pytest.skip("Built local client SDK and Node are required")
    payload = base64.b64decode(json.loads((sdk / "tests/fixtures/image-payload.json").read_text())["payload_base64"])
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    service = SimpleNamespace(startup_status=startup, inference_service=SimpleNamespace(startup_status=lambda _: {
        "status": "running", "phase": "warming_models", "message": "pose",
        "phase_elapsed_seconds": 0.1, "error": None,
    }))
    monkeypatch.setattr(routes, "get_freemocap_app", lambda: service)
    app = FastAPI()
    app.include_router(routes.realtime_router, prefix="/freemocap")
    release = Event()

    async def unused_source():
        return None

    @app.websocket("/test-frames")
    async def frames(websocket: WebSocket):
        await websocket.accept()
        owner = WebsocketServer.__new__(WebsocketServer)
        owner._app = service
        relay = FrameRelay(serializer=SendSerializer(websocket), source=unused_source,
                           should_continue=lambda: True, connection_id="test", on_frame_sent=owner._record_startup_delivery)
        relay.set_composition(compose_messages(StreamContext(skeletons=(), camera_ids=("oak", "zed-left"), pipeline_live=True)))
        await relay._send_frame(FrameContext(frame_number=41, timestamp=1.0, image_payload=payload))
        assert await asyncio.to_thread(release.wait, 3)
        await relay._send_frame(FrameContext(frame_number=41, timestamp=1.0, image_payload=payload,
                                            aggregator_output=AggregationNodeOutputMessage(frame_number=41, pipeline_id="pipeline")))
        await websocket.close()

    with TestClient(app) as client, client.websocket_connect("/test-frames") as socket:
        preview = socket.receive_bytes()
        try:
            pending = client.get("/freemocap/realtime/startup").json()
            assert pending["status"] == "running" and pending["phase"] == "warming_models"
            assert pending["preview_ready"]
        finally:
            release.set()
        packet = socket.receive_bytes()
        assert client.get("/freemocap/realtime/startup").json()["status"] == "ready"

    script = '''
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {createClient,readImagePayload} from './dist/index.js';
let socket; const images=[],errors=[];
const client=createClient({baseUrl:'http://test.invalid',socketFactory:()=>socket={readyState:0,send(){},close(){}}});
client.stream.subscribeToProtocolErrors(error=>errors.push(String(error)));
client.stream.subscribeToImages((bytes,frame)=>images.push({frame,payload:readImagePayload(bytes)}));
client.stream.connect();socket.readyState=1;socket.onopen({});
for (const encoded of JSON.parse(readFileSync(0,'utf8'))) {
 const bytes=Buffer.from(encoded,'base64');
 socket.onmessage({data:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)});
}
client.close();assert.deepEqual(errors,[]);assert.equal(images.length,2);
for (const item of images) {
 assert.equal(item.frame,41);assert.deepEqual(item.payload.images.map(x=>x.cameraId),['oak','zed-left']);
}
console.log('SDK received both camera images for frame 41');
'''
    result = subprocess.run([node, "--input-type=module", "-e", script], cwd=sdk,
                            input=json.dumps([base64.b64encode(item).decode() for item in (preview, packet)]),
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "both camera images" in result.stdout


def test_disconnected_sender_cannot_mark_startup_ready():
    from starlette.websockets import WebSocketState
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    socket = SimpleNamespace(client_state=WebSocketState.DISCONNECTED, application_state=WebSocketState.DISCONNECTED)
    # The concrete serializer only needs send methods when connected.
    socket.send_bytes = socket.send_text = socket.close = AsyncMock()
    callback = Mock()
    async def run():
        relay = FrameRelay(serializer=SendSerializer(socket), source=AsyncMock(), should_continue=lambda: True,
                           connection_id="disconnected", on_frame_sent=callback)
        relay.set_composition(compose_messages(StreamContext(skeletons=())))
        await relay._send_frame(FrameContext(frame_number=1, timestamp=1.0))
    asyncio.run(run())
    callback.assert_not_called()
    assert startup.snapshot()["status"] == "running"


def test_image_delivery_during_model_warmup_does_not_claim_tracking_ready():
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    service = SimpleNamespace(has_result=Mock(return_value=False))
    server = WebsocketServer.__new__(WebsocketServer)
    server._app = SimpleNamespace(startup_status=startup, inference_service=service)
    config = RealtimePipelineConfig()
    config.camera_node_config.skeleton_tracking_enabled = True
    output = AggregationNodeOutputMessage(pipeline_id="pipeline", pipeline_config=config)
    frame = FrameContext(frame_number=1, timestamp=1.0, aggregator_output=output)
    server._record_startup_delivery(frame)
    assert startup.snapshot()["status"] == "running"
    service.has_result.return_value = True
    # A valid empty observation is a processed result even when nobody is visible.
    output.camera_node_outputs["camera"] = CameraNodeOutputMessage(
        camera_id="camera", skeleton_observation=Observation(frame_number=0, image_size=(2, 2)),
    )
    server._record_startup_delivery(frame)
    assert startup.snapshot()["status"] == "ready"


def test_camera_only_pipeline_does_not_wait_for_an_unused_model():
    startup = RealtimeStartupStatus()
    startup.begin()
    startup.pipeline_created("pipeline")
    service = SimpleNamespace(has_result=Mock(return_value=False))
    server = WebsocketServer.__new__(WebsocketServer)
    server._app = SimpleNamespace(startup_status=startup, inference_service=service)
    config = RealtimePipelineConfig()
    config.camera_node_config.skeleton_tracking_enabled = False
    output = AggregationNodeOutputMessage(pipeline_id="pipeline", pipeline_config=config)
    server._record_startup_delivery(FrameContext(frame_number=1, timestamp=1.0, aggregator_output=output))
    assert startup.snapshot()["status"] == "ready"
    service.has_result.assert_not_called()
