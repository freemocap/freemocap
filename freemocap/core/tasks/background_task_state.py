"""Thread-safe, bounded task history; executors still own work and cancellation."""
from _thread import RLock as RLockType
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Literal

from freemocap.core.pipeline.posthoc.task_snapshot import BackgroundTaskSnapshot, TaskProgress
from freemocap.system.recording_structure.recording_structure import RecordingStructure

ACTIVE = ('queued', 'running')


@dataclass
class BackgroundTaskState:
    completed_limit: int = 100
    revision: int = 0
    tasks: dict[str, BackgroundTaskSnapshot] = field(default_factory=dict)
    lock: RLockType = field(default_factory=RLock)

    def register(self, task_id: str, kind: Literal['export', 'sync', 'realtime_startup', 'onnx_preparation'], *,
                 recording: RecordingStructure | None = None,
                 source_run_id: int | None = None, source_revision: str | None = None) -> None:
        with self.lock:
            if task_id in self.tasks:
                raise ValueError(f'Task already registered: {task_id}')
            now = datetime.now(timezone.utc)
            self.tasks[task_id] = BackgroundTaskSnapshot(task_id=task_id, revision=1, task_type=kind,
                recording=recording, source_run_id=source_run_id, source_revision=source_revision,
                status='queued', progress=TaskProgress(phase='queued', progress_fraction=None, detail='Queued'),
                created_at=now, updated_at=now)
            self.revision += 1

    def update(self, task_id: str, **changes) -> None:
        with self.lock:
            previous = self.tasks.get(task_id)
            if previous is None or previous.status not in ACTIVE:
                return  # Terminal observations cannot be overwritten by late worker updates.
            if all(getattr(previous, name) == value for name, value in changes.items()):
                return
            values = previous.model_dump()
            values.update(changes, revision=previous.revision + 1, updated_at=datetime.now(timezone.utc))
            self.tasks[task_id] = BackgroundTaskSnapshot.model_validate(values)
            self.revision += 1
            completed = sorted((task for task in self.tasks.values() if task.status not in ACTIVE),
                               key=lambda task: task.updated_at)
            for task in completed[:max(0, len(completed) - self.completed_limit)]:
                del self.tasks[task.task_id]
                self.revision += 1

    def snapshot(self) -> tuple[int, tuple[BackgroundTaskSnapshot, ...]]:
        with self.lock:
            return self.revision, tuple(task.model_copy(deep=True) for task in self.tasks.values())
