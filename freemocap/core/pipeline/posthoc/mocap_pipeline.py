"""Managed Mocap recording task: group detection, annotation, and reconstruction."""

from freemocap.core.pipeline.performance_report import PerformanceReport
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized
from queue import Empty, Queue
from concurrent.futures import CancelledError

from skellycam.core.ipc.process_management.managed_worker import ManagedWorker, WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, ItemProgressSnapshot, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.operation_progress import OperationProgressReporter
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig



@dataclass(frozen=True, slots=True)
class MocapWorkerRequest:
    pipeline_id: str
    recording: RecordingInfo
    config: PosthocMocapPipelineConfig
    ipc: PipelineIPC
    progress_queue: Queue[PipelineProgressMessage]

    performance: PerformanceReport = field(default_factory=PerformanceReport)
    operation_progress: OperationProgressReporter = field(default_factory=OperationProgressReporter)

    def report(self, stage: str, detail: str, fraction: float) -> None:
        self.operation_progress.report(self, stage, detail, fraction)

    def report_operation(self, operation_id: str, label: str, status: str,
                         detail: str = "", completed: int | None = None,
                         total: int | None = None, unit: str | None = None,
                         *, phase: str = "reconstructing",
                         items: tuple[ItemProgressSnapshot, ...] | None = None) -> None:
        self.operation_progress.update(self, operation_id, label, status, detail,
                                       completed, total, unit, phase=phase, items=items)

    def report_export(self, task_id: str, label: str, state: str, detail: str,
                      completed: int | None = None, total: int | None = None) -> None:
        self.report_operation(task_id, label, state, detail, completed, total,
                              "channels" if total is not None else None,
                              phase="exporting_csv")


def complete_mocap(request: MocapWorkerRequest) -> None:
    """Finish independent exports before reporting the recording's final outcome."""
    from freemocap.core.pipeline.posthoc.export_completion import complete_recording_exports
    complete_recording_exports(request)


def run_mocap_pipeline(*, request: MocapWorkerRequest) -> None:
    outcome = "failed"
    try:
        _run_mocap_pipeline(request=request)
        outcome = "complete" if request.ipc.should_continue else "cancelled"
    except CancelledError:
        outcome = "cancelled"
        return
    finally:
        request.performance.log(pipeline_id=request.pipeline_id, outcome=outcome)


def _run_mocap_pipeline(*, request: MocapWorkerRequest) -> None:
    from freemocap.core.pipeline.dataflow.application_pipeline import run_application_graph
    try:
        run_application_graph(request=request)
    except CancelledError:
        raise
    except Exception as error:
        request.report(AggregatorPhase.FAILED, f"{type(error).__name__}: {error}", 0.0)
        request.ipc.shutdown_pipeline()
        raise


@dataclass
class MocapPipeline(PipelineABC):
    id: str
    recording_info: RecordingInfo
    ipc: PipelineIPC
    worker: ManagedWorker
    progress_queue: Queue[PipelineProgressMessage]
    pipeline_type: PosthocPipelineType = field(default=PosthocPipelineType.MOCAP, init=False)
    started: bool = False
    _latest: dict[str, PipelineProgressMessage] = field(default_factory=dict)

    @classmethod
    def create(
        cls, *, pipeline_id: str, recording_info: RecordingInfo, config: PosthocMocapPipelineConfig,
        worker_registry: WorkerRegistry, global_kill_flag: Synchronized,
    ) -> "MocapPipeline":
        from pathlib import Path
        from freemocap.core.pipeline.dataflow.processing_plan import build_processing_plan
        plan = build_processing_plan(recording_path=Path(recording_info.full_recording_path), config=config)
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp, pipeline_id=pipeline_id)
        progress_queue: Queue[PipelineProgressMessage] = Queue()
        request = MocapWorkerRequest(pipeline_id=pipeline_id, recording=recording_info,
            config=config, ipc=ipc, progress_queue=progress_queue)
        request.operation_progress.initialize(request, plan)
        try:
            worker = worker_registry.create_worker(
                shutdown_flag=ipc.pipeline_shutdown_flag, worker_mode=WorkerMode.THREAD,
                target=run_mocap_pipeline, name=f"Mocap-{pipeline_id}", log_queue=ipc.ws_queue,
                kwargs={"request": request},
            )
        except Exception:
            ipc.shutdown_pipeline()
            raise
        pipeline = cls(id=pipeline_id, recording_info=recording_info, ipc=ipc,
            worker=worker, progress_queue=progress_queue)
        pipeline._latest[pipeline_id] = AggregatorNodeProgressMessage(
            pipeline_id=pipeline_id, pipeline_type=str(PosthocPipelineType.MOCAP),
            phase=AggregatorPhase.SETTING_UP, detail="Mocap pipeline queued",
            plan=plan, operations=tuple(request.operation_progress.operations.values()),
            recording_name=recording_info.recording_name,
            recording_path=str(recording_info.full_recording_path),
        )
        return pipeline

    @property
    def alive(self) -> bool:
        return self.worker.is_alive()

    def start(self) -> None:
        if self.started:
            raise RuntimeError("Mocap pipeline already started")
        self.worker.start()
        self.started = True

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        while True:
            try:
                message = self.progress_queue.get_nowait()
            except Empty:
                break
            self._latest[message.pipeline_id] = message
        exited_without_outcome = self.started and not self.alive and not any(
            message.phase in (AggregatorPhase.COMPLETE, AggregatorPhase.FAILED)
            for message in self._latest.values() if message.pipeline_id == self.id
        )
        if (self.worker.failure_exitcode is not None or exited_without_outcome) and not any(
            message.phase == AggregatorPhase.FAILED for message in self._latest.values() if message.pipeline_id == self.id
        ):
            self._latest[self.id] = AggregatorNodeProgressMessage(
                pipeline_id=self.id, pipeline_type=str(self.pipeline_type), phase=AggregatorPhase.FAILED,
                detail=f"Mocap worker exited without completing the task (exit code {self.worker.exitcode})",
                recording_name=self.recording_info.recording_name,
                recording_path=str(self.recording_info.full_recording_path),
                operations=self._latest[self.id].operations if self.id in self._latest else None,
                timing=self._latest[self.id].timing if self.id in self._latest else None,
                plan=self._latest[self.id].plan if self.id in self._latest else None,
            )
            self.ipc.shutdown_pipeline()
        return list(self._latest.values())

    def drain_and_get_messages(self) -> list[PipelineProgressMessage]:
        return self.get_progress_messages()

    def shutdown(self) -> None:
        self.worker.mark_stopping()
        self.ipc.shutdown_pipeline()
        if self.worker.is_alive():
            self.worker.terminate_gracefully()
        else:
            self.worker._reap()
        if self.worker.is_alive():
            raise RuntimeError("Mocap worker is still shutting down")
