"""
SyncJobManager: lifecycle manager for fire-and-forget video-synchronization jobs.

Mirrors PosthocPipelineManager's shape (create / progress polling / shutdown),
but is much simpler: a sync job is a single worker process with no per-camera
nodes or pubsub, and — unlike posthoc pipelines — its final SyncResult is
needed later by the caller (to copy the synced videos into the recording
folder), so completed jobs are NOT auto-evicted from `jobs`. The worker
process itself is reaped as soon as it exits (to free OS resources) while the
SyncJob object (holding the drained progress/result) stays queryable until the
caller explicitly calls `cleanup_job()` once it's done with the result.
"""
import logging
import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skelly_synchronize.core.models import SyncRequest

from freemocap.core.pipeline.abcs.pipeline_manager_abc import PipelineManagerABC
from freemocap.core.pipeline.posthoc.pipeline_phases import SyncStage
from freemocap.core.pipeline.posthoc.progress_messages import SyncJobProgressMessage
from freemocap.core.pipeline.posthoc.sync_job import SyncJob
from freemocap.core.types.type_overloads import PipelineIdString

logger = logging.getLogger(__name__)


@dataclass
class SyncJobManager(PipelineManagerABC):
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    lock: multiprocessing.synchronize.Lock = field(default_factory=multiprocessing.Lock)
    jobs: dict[PipelineIdString, SyncJob] = field(default_factory=dict)
    _reaped: set[PipelineIdString] = field(default_factory=set)
    pending_stop_messages: list[SyncJobProgressMessage] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Job creation
    # ------------------------------------------------------------------

    def create_job(self, *, request: SyncRequest) -> SyncJob:
        job = SyncJob.create(
            request=request,
            worker_registry=self.worker_registry,
            global_kill_flag=self.global_kill_flag,
        )
        job.queued_message = SyncJobProgressMessage(
            pipeline_id=job.id,
            pipeline_type="sync",
            phase="queued",
            progress_fraction=0.0,
            detail="Synchronization job queued, starting worker...",
        )
        job.started = True
        job.start()
        with self.lock:
            self.jobs[job.id] = job
        logger.info(f"Created sync job [{job.id}]")
        return job

    def get_job(self, job_id: PipelineIdString) -> SyncJob | None:
        return self.jobs.get(job_id)

    def cleanup_job(self, job_id: PipelineIdString) -> None:
        """Remove a job once the caller is done consuming its result."""
        with self.lock:
            job = self.jobs.pop(job_id, None)
            self._reaped.discard(job_id)
        if job is not None and job.is_alive:
            job.shutdown()

    # ------------------------------------------------------------------
    # Progress / reaping
    # ------------------------------------------------------------------

    def _reap_dead(self) -> None:
        """Call must hold self.lock. Reaps finished worker processes exactly once."""
        for job_id, job in self.jobs.items():
            if job_id in self._reaped:
                continue
            if job.started and not job.is_alive:
                job.worker._reap()
                self._reaped.add(job_id)

    def get_progress_updates(self) -> list[SyncJobProgressMessage]:
        with self.lock:
            stop_messages, self.pending_stop_messages = self.pending_stop_messages, []
            self._reap_dead()
            jobs = list(self.jobs.values())

        progress_messages: list[SyncJobProgressMessage] = list(stop_messages)
        for job in jobs:
            queued = getattr(job, "queued_message", None)
            if queued is not None:
                progress_messages.append(queued)
                job.queued_message = None
            progress_messages.extend(job.get_progress_messages())
        return progress_messages

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop_job(self, job_id: PipelineIdString) -> bool:
        with self.lock:
            job = self.jobs.pop(job_id, None)
            self._reaped.discard(job_id)
            if job is not None:
                self.pending_stop_messages.append(SyncJobProgressMessage(
                    pipeline_id=job.id,
                    pipeline_type="sync",
                    phase=str(SyncStage.FAILED),
                    progress_fraction=0.0,
                    detail="Stopped by user",
                ))
        if job is None:
            logger.warning(f"stop_job: sync job [{job_id}] not found")
            return False
        job.shutdown()
        logger.info(f"Stopped sync job [{job_id}]")
        return True

    def shutdown(self) -> None:
        with self.lock:
            for job in self.jobs.values():
                if job.is_alive:
                    job.shutdown()
            self.jobs.clear()
            self._reaped.clear()
        logger.info("SyncJobManager: all jobs shut down")
