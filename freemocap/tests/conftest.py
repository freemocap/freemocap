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
