# Application logging relay

FreeMoCap configures SkellyLogs at application startup. Worker processes retain
the shared multiprocessing log queue; replacing it with a thread queue would
break delivery across spawned processes.

`freemocap/api/websocket/log_relay.py` owns one reader thread in the main
application. It continuously drains that queue, including when no frontend is
connected. Each websocket subscribes to a separate bounded thread queue, so
clients receive broadcasts rather than competing for records. A slow client's
buffer drops its oldest relay copy after 1,000 records. With no clients, relay
copies are discarded. Console/file handlers are unaffected; websocket delivery
is best effort, not a persistent log archive.

`freemocap/__main__.py` starts the reader before workers. Shutdown keeps it alive
through `WorkerRegistry.shutdown_all()`, then drains through a sentinel and
joins the reader. It never cancels a producer's queue feeder or closes the
externally owned SkellyLogs queue. If worker shutdown raises, the reader stays
alive until process exit. Server supervision checks reader health and surfaces
failure instead of silently continuing with a dead consumer.

Validation covers spawned heavy logging without clients, broadcast, slow
clients, unsubscribe/reconnect, reader failures, stop retry, websocket
disconnects, and server shutdown. Run:

```powershell
.\.venv\Scripts\python.exe -B -m pytest freemocap/tests/test_log_relay.py freemocap/tests/test_websocket_disconnect.py freemocap/tests/test_camera_only_websocket.py freemocap/tests/test_server_failure.py -q
```

This change does not alter camera recording finalization or claim durable log
flushing during forced process termination. SkellyForge logging integration is
a separate repository stage after the human commits this core change.
