"""Nonblocking fan-out: app-owned source polling, one bounded worker per output."""
from __future__ import annotations

import asyncio
import threading
from contextlib import suppress
from queue import Empty, Full, Queue
from uuid import uuid4

from freemocap.core.streaming.outputs.contracts import (
    OutputCapability, OutputConflictError, OutputEmitter, OutputSample, OutputSource,
    OutputState, OutputUnavailableError, ProtocolDefinition, StartOutputRequest,
)


class _Output:
    def __init__(self, state: OutputState, emitter: OutputEmitter):
        self.state = state
        self.emitter = emitter
        self.queue: Queue[OutputSample] = Queue(maxsize=state.queue_capacity)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.close_error: str | None = None
        self.cursors: dict[str, int] = {}
        self.thread = threading.Thread(target=self._run, name=f"Output-{state.id}", daemon=True)
        self.thread.start()

    def snapshot(self) -> OutputState:
        with self.lock:
            return self.state.model_copy(deep=True)

    def fail(self, error: str) -> None:
        with self.lock:
            if self.state.status not in ("failed", "stopped"):
                self.state.status = "failed"
                self.state.error = error
            self.stop_event.set()

    def offer(self, sample: OutputSample) -> None:
        with self.lock:
            if self.stop_event.is_set():
                return
            previous = self.cursors.get(sample.pipeline_id)
            if previous is None:
                # One selected source per output; retire old session cursors.
                self.cursors.clear()
            if previous is not None and sample.frame.frame_number <= previous:
                return
            if previous is not None:
                self.state.source_frame_gaps += max(0, sample.frame.frame_number - previous - 1)
            self.cursors[sample.pipeline_id] = sample.frame.frame_number
            self.state.active_pipeline_id = sample.pipeline_id
            try:
                self.queue.put_nowait(sample)
            except Full:
                self.state.queue_overflows += 1
                if self.state.overflow_policy == "fail":
                    self.fail("Output queue overflow; acquisition continues, this output stopped")
                    return
                try:
                    self.queue.get_nowait()
                    self.state.queue_dropped_frames += 1
                except Empty:
                    pass  # The emitter took the previous sample concurrently.
                self.queue.put_nowait(sample)

    def idle(self) -> None:
        with self.lock:
            if self.state.status not in ("failed", "stopped"):
                self.state.status = "idle"
                self.state.active_pipeline_id = None
                self.cursors.clear()

    def _run(self) -> None:
        try:
            while not self.stop_event.is_set():
                try:
                    sample = self.queue.get(timeout=0.05)
                except Empty:
                    continue
                if self.stop_event.is_set():
                    break
                self.emitter.emit(sample)
                with self.lock:
                    self.state.frames_emitted += 1
                    self.state.last_frame_number = sample.frame.frame_number
                    self.state.last_capture_timestamp_ns = str(sample.source_timestamp_ns)
                    if not self.stop_event.is_set() and self.state.active_pipeline_id is not None:
                        self.state.status = "running"
        except Exception as error:
            self.fail(f"{type(error).__name__}: {error}")
        finally:
            # Retained status history must not retain scientific frame buffers.
            while True:
                try:
                    self.queue.get_nowait()
                except Empty:
                    break
            try:
                self.emitter.close()
            except Exception as error:
                with self.lock:
                    self.close_error = str(error)
                    self.state.status = "failed"
                    self.state.error = f"{self.state.error or ''} Close failed: {error}".strip()

    def stop(self) -> OutputState:
        self.stop_event.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            self.fail("Output worker did not stop within two seconds")
            raise RuntimeError(self.state.error)
        if self.close_error is not None:
            raise RuntimeError(f"Output cleanup failed: {self.close_error}")
        with self.lock:
            # Explicit stop retains any previous failure evidence.
            self.state.status = "stopped"
            self.state.active_pipeline_id = None
        return self.snapshot()


class StreamingOutputManager:
    def __init__(self, *, source: OutputSource, protocols: tuple[ProtocolDefinition, ...],
                 poll_interval: float = 0.005):
        self.source = source
        self.protocols = {item.name: item for item in protocols}
        self.outputs: dict[str, _Output] = {}
        self.poll_interval = poll_interval
        self.task: asyncio.Task | None = None
        self.closed = False

    def capabilities(self) -> list[OutputCapability]:
        result = []
        for definition in self.protocols.values():
            reason = definition.unavailable_reason()
            result.append(OutputCapability(protocol=definition.name,
                config_schema=definition.config_type.model_json_schema(),
                overflow_policy=definition.overflow_policy, available=reason is None,
                unavailable_reason=reason))
        return result

    async def start(self, request: StartOutputRequest) -> OutputState:
        if self.closed:
            raise OutputConflictError("Output manager is closed")
        definition = self.protocols[request.protocol]
        config = definition.config_type.model_validate(request.config)
        reason = definition.unavailable_reason()
        if reason is not None:
            raise OutputUnavailableError(reason)
        if request.pipeline_id is None and len(self.source.source_ids()) > 1:
            raise OutputConflictError("Select pipeline_id when multiple sources are active")
        if sum(item.thread.is_alive() for item in self.outputs.values()) >= 16:
            raise OutputConflictError("At most 16 simultaneous outputs are supported")
        # Bound retained history; live/unfinished workers are never evicted.
        for key, item in list(self.outputs.items()):
            if len(self.outputs) < 128:
                break
            if item.stop_event.is_set() and not item.thread.is_alive():
                del self.outputs[key]
        emitter = definition.create(config)
        state = OutputState(id=uuid4().hex, protocol=request.protocol,
            pipeline_id=request.pipeline_id, config=config.model_dump(mode="json"),
            queue_capacity=request.queue_capacity, overflow_policy=definition.overflow_policy)
        try:
            output = _Output(state, emitter)
        except BaseException:
            emitter.close()
            raise
        self.outputs[state.id] = output
        if self.task is None:
            self.task = asyncio.create_task(self._run_source(), name="StreamingOutputSource")
        return output.snapshot()

    def get(self, output_id: str) -> OutputState:
        return self.outputs[output_id].snapshot()

    def list_outputs(self) -> list[OutputState]:
        return [item.snapshot() for item in self.outputs.values()]

    async def stop(self, output_id: str) -> OutputState:
        output = self.outputs[output_id]
        return await asyncio.to_thread(output.stop)

    async def _run_source(self) -> None:
        while not self.closed:
            active = [item for item in self.outputs.values() if not item.stop_event.is_set()]
            if active:
                try:
                    batch = self.source.poll()
                except Exception as error:
                    for output in active:
                        output.fail(f"Source failed: {type(error).__name__}: {error}")
                else:
                    for output in active:
                        selected = output.state.pipeline_id
                        if selected is None:
                            if len(batch.active_sources) > 1:
                                output.fail("Multiple sources became active; restart with pipeline_id")
                                continue
                            selected = next(iter(batch.active_sources), None)
                        if selected in batch.errors:
                            output.fail(f"Source {selected} failed: {batch.errors[selected]}")
                        elif selected not in batch.active_sources:
                            output.idle()
                        else:
                            for sample in batch.samples:
                                if sample.pipeline_id == selected:
                                    output.offer(sample)
            await asyncio.sleep(self.poll_interval)

    def close(self) -> None:
        self.closed = True
        if self.task is not None and not self.task.done():
            self.task.cancel()
        errors = []
        for output in self.outputs.values():
            try:
                output.stop()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Streaming output shutdown failed", errors)

    async def aclose(self) -> None:
        self.closed = True
        if self.task is not None:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        # Joining transport threads must not block the server event loop.
        await asyncio.to_thread(self.close)
