"""Shared helpers for the pipeline end-to-end tests."""
from pathlib import Path
import time

PIPELINE_TIMEOUT_SECONDS = 600.0


def wait_for_pipeline(pipeline, timeout: float = PIPELINE_TIMEOUT_SECONDS) -> None:
    """Poll until a fire-and-forget posthoc pipeline finishes (or time out).

    Posthoc pipelines self-terminate when processing completes; we just watch
    ``.alive`` flip to False.
    """
    start = time.perf_counter()
    while pipeline.alive:
        if time.perf_counter() - start > timeout:
            pipeline.shutdown()
            raise TimeoutError(f"Pipeline [{pipeline.id}] did not complete within {timeout}s")
        time.sleep(0.5)


def find_body_3d_npy(npy_files: list[Path]) -> Path:
    """Pick the body 3D trajectory ``.npy`` from a list of output files.

    Among matches, returns the most-recently-modified file so we validate the
    CURRENT run's output rather than a stale file left over from a previous run
    (e.g. a different calibration board prefix).
    """
    candidates = [f for f in npy_files if "body" in f.stem.lower() and "3d" in f.stem.lower()]
    if not candidates:
        candidates = [f for f in npy_files if "body" in f.stem.lower()]
    if not candidates:
        raise AssertionError(f"No body npy found among: {[f.name for f in npy_files]}")
    return max(candidates, key=lambda f: f.stat().st_mtime)
