"""
SyncJob: a lightweight fire-and-forget job that runs skelly_synchronize's
audio/brightness synchronization pipeline in a worker process.

Unlike PosthocPipeline (per-camera VideoNode processes + an aggregation node),
a sync job is a single call into an external library — so it reuses only the
minimal pieces of the posthoc pipeline machinery: BaseNode's worker lifecycle
and a queue-based progress-reporting convention compatible with the same
frontend progress panel.
"""
import logging
import multiprocessing
import multiprocessing.queues
import uuid
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized
from queue import Empty

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skelly_synchronize.core.exceptions import SkellySyncError
from skelly_synchronize.core.models import SyncRequest, SyncResult

from freemocap.core.pipeline.abcs.base_node_abc import BaseNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.pipeline_phases import SyncStage
from freemocap.core.pipeline.posthoc.progress_messages import SyncJobProgressMessage
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class SyncJob(BaseNode):
    id: PipelineIdString
    progress_subscription: multiprocessing.queues.Queue
    result_subscription: multiprocessing.queues.Queue
    started: bool = False
    queued_message: SyncJobProgressMessage | None = None
    # Cached once the (single) result message has been drained from result_subscription.
    _finished: bool = field(default=False, repr=False)
    _result: SyncResult | None = field(default=None, repr=False)
    _error: str | None = field(default=None, repr=False)

    @classmethod
    def create(
        cls,
        *,
        request: SyncRequest,
        worker_registry: WorkerRegistry,
        global_kill_flag: Synchronized,
    ) -> "SyncJob":
        job_id: PipelineIdString = str(uuid.uuid4())[:6]
        ipc = PipelineIPC.create(
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp,
            pipeline_id=job_id,
        )
        progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        result_queue: multiprocessing.queues.Queue = multiprocessing.Queue()

        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"SyncJob-{job_id}",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            # skelly_synchronize's TrimStage runs a ProcessPoolExecutor internally —
            # Python disallows daemonic processes from spawning their own children,
            # so this worker must NOT be daemonic (unlike most other pipeline nodes).
            daemon=False,
            kwargs=dict(
                job_id=job_id,
                request=request,
                progress_pub=progress_queue,
                result_pub=result_queue,
            ),
        )
        return cls(
            id=job_id,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
            progress_subscription=progress_queue,
            result_subscription=result_queue,
        )

    @staticmethod
    def _run(
        *,
        job_id: PipelineIdString,
        request: SyncRequest,
        progress_pub: "multiprocessing.queues.Queue",
        result_pub: "multiprocessing.queues.Queue",
        shutdown_self_flag: Synchronized,  # noqa: ARG004 - injected by BaseNode._create_worker
    ) -> None:
        # Imported inside the child process (rather than at module scope) so the
        # (fairly heavy) librosa/scipy/opencv import chain only happens in workers
        # that actually run a sync job, not on every posthoc-pipeline child spawn.
        from skelly_synchronize.core.pipeline.runner import run_pipeline

        def _emit(stage: SyncStage, detail: str, fraction: float) -> None:
            progress_pub.put(SyncJobProgressMessage(
                pipeline_id=job_id,
                pipeline_type="sync",
                phase=str(stage),
                progress_fraction=fraction,
                detail=detail,
            ))

        def _progress_callback(video_name: str, fraction: float) -> None:
            _emit(SyncStage.TRIMMING, f"Trimming {video_name}", fraction)

        _emit(SyncStage.PROBING, "Probing and analyzing videos...", 0.0)
        try:
            result = run_pipeline(request, progress_callback=_progress_callback)
            result_pub.put(("ok", result))
            _emit(SyncStage.COMPLETE, "Synchronization complete", 1.0)
        except SkellySyncError as e:
            logger.error(f"SyncJob [{job_id}] failed: {e}", exc_info=True)
            result_pub.put(("error", str(e)))
            _emit(SyncStage.FAILED, str(e), 0.0)
        except Exception as e:
            logger.error(f"SyncJob [{job_id}] failed unexpectedly: {e}", exc_info=True)
            result_pub.put(("error", f"{type(e).__name__}: {e}"))
            _emit(SyncStage.FAILED, str(e), 0.0)

    def get_progress_messages(self) -> list[SyncJobProgressMessage]:
        messages: list[SyncJobProgressMessage] = []
        while True:
            try:
                messages.append(self.progress_subscription.get_nowait())
            except Empty:
                break
        return messages

    def poll_result(self) -> None:
        """Drain the (at most one) result message. Safe to call repeatedly."""
        if self._finished:
            return
        try:
            status, payload = self.result_subscription.get_nowait()
        except Empty:
            return
        self._finished = True
        if status == "ok":
            self._result = payload
        else:
            self._error = payload

    @property
    def finished(self) -> bool:
        self.poll_result()
        return self._finished

    @property
    def result(self) -> SyncResult | None:
        self.poll_result()
        return self._result

    @property
    def error(self) -> str | None:
        self.poll_result()
        return self._error
