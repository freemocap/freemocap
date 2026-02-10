"""
BaseNode: common lifecycle for all pipeline processing nodes.

Every node (realtime camera, realtime aggregation, video, posthoc aggregation)
owns a ManagedProcess and a shutdown flag. BaseNode provides start() and
shutdown() so subclasses don't have to reimplement them.
"""
import logging
import multiprocessing
from dataclasses import dataclass

from skellycam.core.ipc.process_management.managed_process import ManagedProcess

logger = logging.getLogger(__name__)


@dataclass
class BaseNode:
    """
    Common base for all pipeline nodes.

    Subclasses must provide:
      - shutdown_self_flag: multiprocessing.Value('b', False)
      - worker: ManagedProcess
    via their own create() classmethod.
    """
    shutdown_self_flag: multiprocessing.Value
    worker: ManagedProcess

    def start(self) -> None:
        logger.debug(f"Starting {self.__class__.__name__} (worker: {self.worker.name})")
        self.worker.start()

    def shutdown(self) -> None:
        logger.debug(f"Shutting down {self.__class__.__name__} (worker: {self.worker.name})")
        self.shutdown_self_flag.value = True
        self.worker.terminate_gracefully()
        logger.debug(f"{self.__class__.__name__} (worker: {self.worker.name}) shut down")

    @property
    def is_alive(self) -> bool:
        return self.worker.is_alive()
