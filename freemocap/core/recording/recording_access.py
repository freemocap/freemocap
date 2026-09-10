"""Coordinate recording readers and exclusive posthoc ownership in the server process."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from freemocap.system.recording_structure.recording_structure import RecordingStructure


class RecordingOwner(BaseModel):
    model_config = ConfigDict(frozen=True)
    recording: RecordingStructure
    task_id: str


class RecordingBusyError(RuntimeError):
    def __init__(self, *, owner: RecordingOwner) -> None:
        self.owner = owner
        super().__init__(
            f"Recording is owned by processing task {owner.task_id}: {owner.recording.full_path}"
        )


@dataclass
class RecordingAccess:
    lock: RLock = field(default_factory=RLock)
    owners: dict[Path, RecordingOwner] = field(default_factory=dict)
    readers: dict[UUID, tuple[Path, Callable[[], None]]] = field(default_factory=dict)
    revision: int = 0

    @staticmethod
    def overlaps(*, first: Path, second: Path) -> bool:
        return first == second or first in second.parents or second in first.parents

    def reserve(self, *, recording: RecordingStructure, task_id: str) -> None:
        path = recording.full_path.expanduser().resolve()
        with self.lock:
            for owned_path, owner in self.owners.items():
                if self.overlaps(first=path, second=owned_path):
                    raise RecordingBusyError(owner=owner)
            self.owners[path] = RecordingOwner(
                recording=RecordingStructure(
                    base_directory=path.parent, recording_name=path.name
                ),
                task_id=task_id,
            )
            self.revision += 1
            callbacks = [
                cancel
                for reader_path, cancel in self.readers.values()
                if self.overlaps(first=path, second=reader_path)
            ]
        for cancel in callbacks:
            cancel()

    def ready(self, *, task_id: str) -> bool:
        with self.lock:
            path = next(
                path for path, owner in self.owners.items() if owner.task_id == task_id
            )
            return not any(
                self.overlaps(first=path, second=reader_path)
                for reader_path, _ in self.readers.values()
            )

    def release(self, *, task_id: str) -> None:
        with self.lock:
            path = next(
                path for path, owner in self.owners.items() if owner.task_id == task_id
            )
            del self.owners[path]
            self.revision += 1

    @contextmanager
    def read(self, *, path: Path, cancel: Callable[[], None]) -> Iterator[None]:
        path = path.expanduser().resolve()
        token = uuid4()
        with self.lock:
            for owned_path, owner in self.owners.items():
                if self.overlaps(first=path, second=owned_path):
                    raise RecordingBusyError(owner=owner)
            self.readers[token] = (path, cancel)
        try:
            yield
        finally:
            with self.lock:
                del self.readers[token]

    def snapshot(self) -> tuple[RecordingOwner, ...]:
        with self.lock:
            return tuple(owner.model_copy(deep=True) for owner in self.owners.values())
