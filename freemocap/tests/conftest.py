"""Session-wide test setup.

Lives at the test-package root so every test gets it, including ones that never touch
the pipeline fixtures.
"""

import pytest
from tempfile import mkdtemp
from skellylogs.handlers.websocket_log_queue_handler import create_websocket_log_queue


def pytest_configure(config):
    """Use fresh scratch space instead of a Windows temp root shared across users."""
    if config.option.basetemp is not None:
        return
    # Keep video paths below Windows limits; avoid pytest's shared per-user root.
    config.option.basetemp = mkdtemp(prefix="fmc-")


@pytest.fixture(scope="session", autouse=True)
def websocket_log_queue() -> None:
    """Create the websocket log queue before any test runs.

    `PipelineIPC.__init__` calls `get_websocket_log_queue()` unconditionally, and that
    raises `ValueError: Websocket log queue not created yet` unless something created it
    first. In the real app `configure_logging()` does that at startup; tests never call it,
    so anything that stands up a pipeline dies on construction.

    Autouse and session-scoped rather than opt-in, because the failure mode is a new test
    file forgetting a fixture it has no reason to know about. The call is idempotent.
    """
    create_websocket_log_queue()


def pytest_sessionfinish(session, exitstatus):
    """Prevent leftover multiprocessing.Queue feeder threads from hanging exit.

    Every multiprocessing.Queue registers an untimed atexit finalizer that
    joins its internal feeder thread regardless of daemon status. Across the
    e2e/slow pipeline tests, dozens of Queues get created (pubsub topics,
    per-node progress queues, skellylogs' process-wide websocket log queue,
    skellycam's own camera-event pubsub, ...); some end up with a feeder
    thread parked forever writing to a pipe nobody reads anymore (e.g. a
    child process died, or -- for the websocket log queue -- nothing ever
    drains it in a plain pytest run once its OS pipe buffer fills). Any one
    of those makes Py_FinalizeEx block forever, so pytest prints its summary
    but the process never exits (see PR #896 CI investigation).

    We've since closed off several of these leaks at the source (see
    freemocap/pubsub/pubsub_abcs.py and
    freemocap/core/pipeline/abcs/base_node_abc.py), but some live in
    third-party dependencies (skellycam, skellylogs) we don't control from
    here. This sweep is the reliable backstop: cancel every live Queue's
    join-thread finalizer at session end so exit can never hang on one we
    missed.

    Unlike the two source-level fixes above (which skip the flush-wait while
    the app could still be running), this one is unconditionally safe: it
    only runs once the whole pytest session is ending, so by definition
    nothing is left to read a message anyway, flushed or not.
    """
    import gc
    import multiprocessing.queues

    for obj in gc.get_objects():
        if isinstance(obj, multiprocessing.queues.Queue):
            try:
                obj.cancel_join_thread()
            except Exception:
                pass
