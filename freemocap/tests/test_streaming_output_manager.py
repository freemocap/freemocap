import asyncio
import threading
import time
from collections import deque

import pytest
from pydantic import BaseModel

from freemocap.core.streaming.message_model import FrameMessage
from freemocap.core.streaming.outputs.contracts import (
    OutputConflictError, OutputSample, ProtocolDefinition, SourceBatch, StartOutputRequest,
)
from freemocap.core.streaming.outputs.manager import StreamingOutputManager


class Config(BaseModel):
    pass


class Source:
    def __init__(self):
        self.ids = ("a",)
        self.pending = deque()

    def source_ids(self):
        return self.ids

    def poll(self):
        samples = tuple(self.pending)
        self.pending.clear()
        return SourceBatch(samples, self.ids)

    def put(self, number, pipeline="a"):
        sample = OutputSample(FrameMessage(frame_number=number), pipeline,
                              9_007_199_254_740_993 + number, (("camera", 1_000_000_001 + number),))
        self.pending.append(sample)
        return sample


class Emitter:
    def __init__(self, *, blocked=False, broken=False):
        self.samples = []
        self.closed = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.blocked = blocked
        self.broken = broken

    def emit(self, sample):
        self.entered.set()
        if self.blocked:
            if not self.release.wait(10):
                raise TimeoutError("Test emitter release missing")
        if self.broken:
            raise OSError("receiver error")
        self.samples.append(sample)

    def close(self):
        self.closed = True


def definition(name, emitter, policy="fail"):
    return ProtocolDefinition(name, Config, lambda config: emitter, policy)


async def until(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline, "Timed out waiting for owned output"
        await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_idle_start_capture_stop_reconnect_and_explicit_shutdown():
    source, emitter = Source(), Emitter()
    source.ids = ()
    manager = StreamingOutputManager(source=source, protocols=(definition("lsl", emitter),))
    try:
        state = await manager.start(StartOutputRequest(protocol="lsl"))
        assert state.status == "idle"
        source.ids = ("a",)
        expected = source.put(3)
        await until(lambda: len(emitter.samples) == 1)
        assert emitter.samples[0] is expected
        assert manager.get(state.id).last_capture_timestamp_ns == str(expected.source_timestamp_ns)
        assert manager.get(state.id).status == "running"
        source.ids = ()
        await until(lambda: manager.get(state.id).status == "idle")
        assert not emitter.closed  # Camera stop is not output deletion.
        source.ids = ("new-session",)
        source.put(0, "new-session")
        await until(lambda: len(emitter.samples) == 2)
        source.ids = ("a",)
        source.put(0, "a")
        await until(lambda: len(emitter.samples) == 3)
        assert manager.outputs[state.id].cursors == {"a": 0}
        source.ids = ()
        await until(lambda: manager.get(state.id).status == "idle")
        source.ids = ("a",)
        source.put(0, "a")
        await until(lambda: len(emitter.samples) == 4)
        assert (await manager.stop(state.id)).status == "stopped"
        assert (await manager.stop(state.id)).status == "stopped"
        assert emitter.closed
        assert not manager.outputs[state.id].thread.is_alive()
    finally:
        await manager.aclose()
    assert manager.task.done()


@pytest.mark.asyncio
async def test_slow_lsl_fails_without_blocking_other_output_or_retiming_sample():
    source = Source()
    slow, fast = Emitter(blocked=True), Emitter()
    manager = StreamingOutputManager(source=source, protocols=(definition("slow", slow), definition("fast", fast)))
    try:
        a = await manager.start(StartOutputRequest(protocol="slow", queue_capacity=1))
        b = await manager.start(StartOutputRequest(protocol="fast"))
        original = source.put(0)
        await until(slow.entered.is_set)
        source.put(1)
        await until(lambda: manager.outputs[a.id].queue.qsize() == 1)
        source.put(2)
        await until(lambda: manager.get(a.id).status == "failed")
        await until(lambda: len(fast.samples) == 3)
        assert manager.get(a.id).queue_overflows == 1
        assert manager.get(b.id).error is None
        assert fast.samples[0] is original
        slow.release.set()
        await until(lambda: slow.closed)
        assert manager.outputs[a.id].queue.empty()
        assert slow.samples[0].source_timestamp_ns == original.source_timestamp_ns
    finally:
        slow.release.set()
        await manager.aclose()


@pytest.mark.asyncio
async def test_latest_policy_reports_drops_and_emits_newest_pose():
    source, emitter = Source(), Emitter(blocked=True)
    manager = StreamingOutputManager(source=source, protocols=(definition("vmc", emitter, "latest"),))
    try:
        state = await manager.start(StartOutputRequest(protocol="vmc", queue_capacity=1))
        source.put(0)
        await until(emitter.entered.is_set)
        source.put(2)
        await until(lambda: manager.outputs[state.id].queue.qsize() == 1)
        newest = source.put(3)
        await until(lambda: manager.get(state.id).queue_overflows == 1)
        emitter.release.set()
        await until(lambda: len(emitter.samples) == 2)
        assert emitter.samples[-1] is newest
        observed = manager.get(state.id)
        assert observed.queue_dropped_frames == 1
        assert observed.source_frame_gaps == 1
        assert observed.error is None
    finally:
        emitter.release.set()
        await manager.aclose()


@pytest.mark.asyncio
async def test_transport_error_is_scoped_and_source_selection_is_explicit():
    source, bad, good = Source(), Emitter(broken=True), Emitter()
    source.ids = ("a", "b")
    manager = StreamingOutputManager(source=source, protocols=(definition("bad", bad), definition("good", good)))
    try:
        with pytest.raises(OutputConflictError):
            await manager.start(StartOutputRequest(protocol="good"))
        a = await manager.start(StartOutputRequest(protocol="bad", pipeline_id="a"))
        b = await manager.start(StartOutputRequest(protocol="good", pipeline_id="b"))
        source.put(9, "a")
        source.put(1, "b")
        await until(lambda: manager.get(a.id).status == "failed" and len(good.samples) == 1)
        assert "receiver error" in manager.get(a.id).error
        assert manager.get(b.id).last_frame_number == 1
        assert bad.closed
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_failed_but_unfinished_workers_still_count_toward_resource_limit():
    source = Source()
    emitters = []

    def create(config):
        emitter = Emitter(blocked=True)
        emitters.append(emitter)
        return emitter

    manager = StreamingOutputManager(source=source,
        protocols=(ProtocolDefinition("slow", Config, create, "fail"),))
    try:
        for _ in range(16):
            await manager.start(StartOutputRequest(protocol="slow", queue_capacity=1))
        source.put(0)
        await until(lambda: all(emitter.entered.is_set() for emitter in emitters))
        source.put(1)
        source.put(2)
        await until(lambda: all(state.status == "failed" for state in manager.list_outputs()))
        with pytest.raises(OutputConflictError):
            await manager.start(StartOutputRequest(protocol="slow"))
        assert len(emitters) == 16
    finally:
        for emitter in emitters:
            emitter.release.set()
        await manager.aclose()
    assert all(emitter.closed for emitter in emitters)
