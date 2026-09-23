"""Shared helpers for the pipeline end-to-end tests."""
import logging
import time

logger = logging.getLogger(__name__)

PIPELINE_TIMEOUT_SECONDS = 600.0


def wait_for_pipeline(pipeline, timeout: float = PIPELINE_TIMEOUT_SECONDS) -> None:
    """Poll until a fire-and-forget posthoc pipeline finishes (or time out)."""
    logger.info(f"Waiting for pipeline [{pipeline.id}] to complete (timeout={timeout}s)...")
    start = time.perf_counter()
    last_log = start
    while pipeline.alive:
        elapsed = time.perf_counter() - start
        if elapsed > timeout:
            pipeline.shutdown()
            raise TimeoutError(f"Pipeline [{pipeline.id}] did not complete within {timeout}s")
        now = time.perf_counter()
        if now - last_log >= 10.0:
            logger.info(f"  ... still running [{pipeline.id}] ({elapsed:.0f}s elapsed)")
            last_log = now
        time.sleep(0.5)
    elapsed = time.perf_counter() - start
    logger.info(f"Pipeline [{pipeline.id}] completed in {elapsed:.1f}s")
