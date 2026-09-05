# SkellyCam payload ownership validation

Implementation belongs entirely to SkellyCam. FreeMoCap requires no runtime workaround.

Each frontend payload owns a distinct bytearray and returns a read-only memoryview after assembly.
The builder never reuses published storage. Multiple camera groups and websocket connections can
retain payloads across suspended sends without aliasing. Buffer growth occurs before view export.
This avoids the final payload copy but allocates per payload; it is not end-to-end zero-copy networking.
Pooling would require explicit lifetime management and measured benefit before introduction.

Websocket payload selection now keeps frame cursors per camera group. The existing acknowledgment
message still identifies only a frame number: per-group acknowledgment/backpressure is not solved by
this change. A separate SkellyCam protocol/UI change must carry unambiguous acknowledgment identity.

Validation: 16 focused tests passed for payload wire structure, independently retained buffers,
growing subsequent payloads, multi-group cursor selection, a suspended websocket send while another
client builds data, and websocket framerate internals. These use real payload serialization and a
controlled fake websocket; hardware capture and a live browser/network run have not been exercised.
The broader two-file run exposed an unrelated recording filename assertion (`idx0` versus `idx-0`).
Dependency deprecation warnings also remain. Payload/test Ruff checks passed.

The user confirmed cameras work after the fix. This establishes user-reported live camera operation;
the number of groups/clients and slow-client behavior were not specified.

Pause posthoc implementation for user check-in. Additional live acceptance: two groups at different rates,
two browser clients, and a slow/disconnected client; verify images, memory use and throughput. Reconcile
the plans index before resuming canonical observation/timing ingestion and saved-data execution.
