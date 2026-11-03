"""Retain complete operation snapshots before delivery can coalesce updates."""

from dataclasses import dataclass, field
from _thread import RLock
from time import perf_counter

from freemocap.core.pipeline.dataflow.processing_plan import ProcessingPlan
from freemocap.core.pipeline.posthoc.progress_messages import (
    AggregatorNodeProgressMessage,
    OperationProgressSnapshot,
    RunTimingSnapshot,
)


@dataclass
class OperationProgressReporter:
    operations: dict[str, OperationProgressSnapshot] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock)
    started_seconds: dict[str, float] = field(default_factory=dict)

    plan: ProcessingPlan | None = None

    def initialize(self, request, plan: ProcessingPlan) -> None:
        """Operation identity is exactly graph node identity, in compiled graph order."""
        from freemocap.core.pipeline.dataflow.application_pipeline import describe_active_operation
        with self.lock:
            if self.operations:
                raise ValueError('Cannot replace an executing operation plan')
            self.plan = plan
            nodes = {node.id: node for node in plan.graph.nodes}
            for name in plan.topological_order:
                node = nodes[name]
                parents = tuple(dict.fromkeys(edge.source.node for edge in plan.graph.edges if edge.target.node == name))
                self.operations[name] = OperationProgressSnapshot(operation_id=name,
                    label=describe_active_operation(name), status='waiting', stage=node.stage,
                    effects=node.effects, dependencies=parents, waiting_for=parents)
            self.report(request, 'setting_up', 'Processing plan ready; waiting to start', 0.0)

    def artifacts(self, request, operation_id: str, *, reads=(), writes=()) -> None:
        with self.lock:
            operation = self.operations.get(operation_id)
            if operation is not None:
                self.operations[operation_id] = operation.model_copy(update={
                    'files_read': tuple(dict.fromkeys((*operation.files_read, *map(str, reads)))),
                    'files_written': tuple(dict.fromkeys((*operation.files_written, *map(str, writes)))),
                })

    def report(self, request, stage: str, detail: str, fraction: float) -> None:
        # Snapshot construction and queue insertion share a lock so concurrent
        # producers cannot publish an older snapshot after a newer one.
        with self.lock:
            performance = getattr(request, "performance", None)
            timing = None
            if performance is not None:
                elapsed = performance.elapsed_seconds
                frames = performance.frames or None
                timing = RunTimingSnapshot(elapsed_seconds=elapsed, motion_frame_count=frames,
                    seconds_per_motion_frame=elapsed / frames if stage == "complete" and frames else None)
            request.progress_queue.put(AggregatorNodeProgressMessage(
                pipeline_id=request.pipeline_id, pipeline_type="mocap",
                phase=stage, detail=detail, progress_fraction=fraction,
                recording_name=request.recording.recording_name,
                recording_path=str(request.recording.full_recording_path),
                operations=tuple(self.operations.values()),
                timing=timing, plan=self.plan,
            ))

    def update(self, request, operation_id: str, label: str, status: str,
               detail: str = "", completed: int | None = None,
               total: int | None = None, unit: str | None = None,
               *, phase: str = "reconstructing") -> None:
        if completed is not None and total is not None and completed > total:
            raise ValueError("Completed work cannot exceed total work")
        fraction = completed / total if completed is not None and total else None
        with self.lock:
            previous = self.operations.get(operation_id)
            if self.plan is not None and previous is None:
                raise ValueError(f"Operation is absent from the admitted plan: {operation_id}")
            now = perf_counter()
            if status == "running":
                self.started_seconds.setdefault(operation_id, now)
            started = self.started_seconds.get(operation_id)
            elapsed = max(0.0, now - started) if started is not None else None
            if previous is not None and previous.status in ("complete", "failed", "cancelled"):
                elapsed = previous.elapsed_seconds
            if previous is not None and completed is None and total is None:
                completed, total, unit = previous.completed, previous.total, previous.unit
                fraction = previous.progress_fraction
            if status == "complete":
                fraction = 1.0
                if total is not None:
                    completed = total
            self.operations[operation_id] = OperationProgressSnapshot(
                operation_id=operation_id, label=label, status=status,
                **({key: getattr(previous, key) for key in ("stage", "effects", "dependencies", "waiting_for", "files_read", "files_written")} if previous else {}),
                progress_fraction=fraction, detail=detail,
                completed=completed, total=total, unit=unit,
                elapsed_seconds=elapsed,
                seconds_per_motion_frame=(elapsed / request.performance.frames
                    if status == "complete" and elapsed is not None
                    and getattr(request, "performance", None) is not None and request.performance.frames else None),
            )
            if self.plan is not None:
                for name, operation in tuple(self.operations.items()):
                    waiting = tuple(parent for parent in operation.dependencies if self.operations[parent].status != 'complete') if operation.status == 'waiting' else ()
                    self.operations[name] = operation.model_copy(update={'waiting_for': waiting})
            self.report(request, phase, detail, 0.0)
