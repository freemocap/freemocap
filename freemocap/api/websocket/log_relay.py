"""One application-owned IPC log reader; websocket clients never read IPC directly.

Keep this reader alive until every producer has exited. Per-client buffers are
best-effort relay copies; console/file handlers remain the durable logging path.
"""
from contextlib import contextmanager
from queue import Empty, Full, Queue
from threading import Lock, Thread
from uuid import uuid4

CLIENT_LOG_BACKLOG = 1000
RELAY_STOP_TIMEOUT_SECONDS = 5.0


class LogRelay:
    def __init__(self, source, *, client_backlog=CLIENT_LOG_BACKLOG):
        if client_backlog < 1:
            raise ValueError('Client log backlog must be positive')
        self._source = source
        self._client_backlog = client_backlog
        self._clients = set()
        self._lock = Lock()
        self._error = None
        self._stopped = False
        self._closing = False
        self._stop_sent = False
        self._sentinel = ('freemocap.log-relay.stop', uuid4().hex)
        self._thread = Thread(target=self._consume, name='FreeMoCapLogReader', daemon=True)
        self.received = 0
        self.dropped_without_clients = 0
        self.dropped_slow_clients = 0

    def start(self):
        self._thread.start()

    def check_health(self):
        if self._error is not None:
            raise RuntimeError('Application log queue reader failed') from self._error

    @contextmanager
    def subscribe(self):
        self.check_health()
        queue = Queue(maxsize=self._client_backlog)
        with self._lock:
            if self._closing:
                raise RuntimeError('Log relay has stopped')
            self._clients.add(queue)
        try:
            yield queue
        finally:
            with self._lock:
                self._clients.discard(queue)

    def _consume(self):
        try:
            while True:
                record = self._source.get()
                if isinstance(record, tuple) and record == self._sentinel:
                    return
                if not isinstance(record, dict):
                    continue
                with self._lock:
                    self.received += 1
                    if not self._clients:
                        self.dropped_without_clients += 1
                    for client in self._clients:
                        try:
                            client.put_nowait(record)
                        except Full:
                            # Keep the latest diagnostics without blocking other clients.
                            try:
                                client.get_nowait()
                            except Empty:
                                pass
                            client.put_nowait(record)
                            self.dropped_slow_clients += 1
        except Exception as error:
            self._error = error

    def stop(self):
        """Call only after producer workers have joined; drain through a sentinel.

        Does not close the externally owned SkellyLogs queue or cancel its feeder.
        The main-process sentinel follows its earlier records; joined producer
        feeders have already delivered theirs before this method is called.
        """
        self.check_health()
        with self._lock:
            if self._stopped:
                return
            self._closing = True
        if not self._stop_sent:
            self._source.put(self._sentinel, timeout=RELAY_STOP_TIMEOUT_SECONDS)
            self._stop_sent = True
        self._thread.join(timeout=RELAY_STOP_TIMEOUT_SECONDS)
        self.check_health()
        if self._thread.is_alive():
            raise RuntimeError('Application log queue reader did not stop')
        with self._lock:
            self._stopped = True
            self._clients.clear()
