"""
BaseNode: abstract base for all pipeline nodes (realtime and posthoc).

Encapsulates the common lifecycle pattern shared by every node:
  - A `shutdown_self_flag` (per-node shutdown signal)
  - A `worker` (ManagedProcess wrapping the child process)
  - `start()` / `shutdown()` / `is_alive` lifecycle methods

Subclasses implement a `@classmethod create()` factory that calls
`_create_worker()` to build the ManagedProcess, and a `@staticmethod _run()`
that contains the child-side logic. The `_run()` method receives the
`shutdown_self_flag` as a kwarg and should poll it alongside `ipc.should_continue`
in its main loop.

Error escalation policy (enforced by subclasses, not the base):
  - Posthoc nodes: on exception, call `ipc.shutdown_pipeline()` (pipeline-local)
  - Realtime nodes: on exception, call `ipc.kill_everything()` (app-level)
"""
import logging
import multiprocessing
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional, ClassVar

from skellycam.core.ipc.process_management.managed_process import ManagedProcess
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)

# On Windows, multiprocessing.spawn causes each child process to
# re-import the full module tree. Spawning many children simultaneously
# creates a file-locking race (PermissionError) because Windows holds
# brief exclusive locks during file reads, and antivirus real-time
# scanning amplifies the contention. Staggering spawns lets each child
# finish its import phase before the next one starts.
_SPAWN_STAGGER_SECONDS: ClassVar[float] = 0.25 if sys.platform == "win32" else 0.0

@dataclass
class BaseNode:
    """
    Base class for all pipeline worker nodes.

    Every node owns a ManagedProcess and a per-node shutdown flag.
    The common lifecycle (start / shutdown / is_alive) is implemented here
    so subclasses only need to define `create()` and `_run()`.
    """

    shutdown_self_flag: multiprocessing.Value = field(repr=False)
    worker: ManagedProcess = field(repr=False)

    @property
    def is_alive(self) -> bool:
        return self.worker.is_alive()

    def start(self) -> None:
        """Start the child process. Raises if already started."""
        if self.worker.is_alive():
            raise RuntimeError(
                f"{type(self).__name__} worker '{self.worker.name}' is already running"
            )

        if _SPAWN_STAGGER_SECONDS > 0:
            time.sleep(_SPAWN_STAGGER_SECONDS)
        self.worker.start()
        logger.debug(f"{type(self).__name__} worker '{self.worker.name}' started")

    def shutdown(self) -> None:
        """
        Signal the node to stop, then escalate through SIGTERM → SIGKILL.

        Sets the per-node shutdown flag first (so the child's main loop can
        exit cleanly), then delegates to ManagedProcess.terminate_gracefully()
        for escalating force.
        """
        self.shutdown_self_flag.value = True
        self.worker._intentionally_terminated = True
        if self.worker.is_alive():
            logger.debug(f"Shutting down {type(self).__name__} worker '{self.worker.name}'")
            self.worker.terminate_gracefully()
        else:
            self.worker._reap()

    @staticmethod
    def _create_worker(
        *,
        target: Callable[..., None],
        name: str,
        process_registry: ProcessRegistry,
        log_queue: Optional[multiprocessing.Queue],
        kwargs: dict,
    ) -> tuple[multiprocessing.Value, ManagedProcess]:
        """
        Convenience helper for subclass `create()` methods.

        Creates a shutdown_self_flag + ManagedProcess pair with consistent
        setup. The shutdown_self_flag is automatically injected into kwargs
        so the child _run() receives it.

        Returns:
            (shutdown_self_flag, worker) tuple for passing to the dataclass constructor.
        """
        shutdown_self_flag: multiprocessing.Value = multiprocessing.Value('b', False)
        kwargs["shutdown_self_flag"] = shutdown_self_flag
        worker = process_registry.create_process(
            target=target,
            name=name,
            log_queue=log_queue,
            kwargs=kwargs,
        )
        return shutdown_self_flag, worker