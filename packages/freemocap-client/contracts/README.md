# Server contract conformance

This is the reviewed inventory for the accepted W3 integration, not a replacement
protocol or a generated-output correctness oracle. `operations.json` records every
public HTTP operation plus explicit hidden/utility/compatibility classification and
bidirectional WebSocket interactions. Its baseline and W3 artifact hashes identify
the source inventory. Update it deliberately when the accepted server contract changes.

## Independent expectations

| Rule | Owning definition | Independent expected evidence | Test location |
| --- | --- | --- | --- |
| A frame decodes alone | message-protocol; message_model.FrameMessage | a fresh decoder interprets a hand-authored generic model | public-contract.test.ts |
| Ordered identities and columns | ontology; ChannelBlock; tensor contract | explicit distinct model names and numeric XYZ offsets | public-contract.test.ts |
| Byte order and memory | cbor-codec; frame-resolution; worker transfer | literal IEEE754 little-endian bytes; retained first frame stays unchanged | public-contract.test.ts |
| Metadata identity | connection-ownership; snapshot reconciliation | equal content reuses identity; changed content with same counters replaces it | public-contract.test.ts |
| Unsupported versus malformed | message-contract.parseMessage | unsupported kind/version returns null, malformed known frame throws | public-contract.test.ts |
| HTTP verbs and side effects | W3 route migration and owning handlers | explicit POST shutdown/stop, PUT pause, typed 202 exports, GET assets | SDK HTTP conformance |
| Recording location and content | RECORDING_CONTRACT; recording_location | alternate parents and encoded IDs retained; run differs from revision | SDK HTTP conformance |
| Tasks and cancellation | task_interface; task_snapshot | acceptance is not terminal; request abort does not cancel task | SDK HTTP/WS conformance |
| Assets | playback readers; read leases | byte ranges/content types preserved; no filesystem path assumed HTTP URL | SDK HTTP conformance |

`public-contract.test.ts` exercises the application's SDK boundary. The standalone
package carries the same independent transport expectations, HTTP/socket cases,
recording tests and negative TypeScript cases. Existing receive-reuse,
reconciliation and worker-transfer tests remain application regressions.

All operations need serialization, success/error and lifecycle coverage. Iterating
this inventory proves coverage, not behavioral correctness: separately authored
expected URLs/bodies/statuses and real reference workflows supply that evidence.
Actual disk/camera/Blender operations require integration acceptance, not a mock pass.

Full application version is not a unique API fingerprint: W3 changed contracts
without changing every version label. HTTP compatibility must name the reviewed
baseline and supported operations. WebSocket shape version 0 does not imply every
HTTP server with version 0 exists or is compatible. Session provider dictionaries
remain open; image/media decoding support depends on the client runtime.

SDK bindings use the exact operation IDs in operations.json. HTTP conformance runs
against createClient; transport tests retain literal-byte independent expectations.

## Completed development acceptance

SDK `0.1.0-dev.0` provides all 59 typed public operations, raw-response variants,
explicit hidden utilities and all five WebSocket message kinds. Its
`contracts/coverage.md` verifies every operation binding against this ledger.
`compatibility/0.1.0-dev.0.json` records exact baselines, fingerprints, test scope
and limitations. The package remains private and unpublished.

Core integration runners exercise the SDK against private copies of both reference
recordings, actual HTTP/WS task/export/resource lifecycles, canonical-encoded
recorded-channel socket replay, four-camera CUDA capture and the production app.
These complement the conformance tests; they do not claim every external application
side effect was run. Source datasets remain unchanged and server cleanup is checked.

## Output controls

The inventory includes five additive streaming output controls (64 total). See
`operations.json.output_control_delta` for baseline provenance. Use the generated
`streaming_list_protocols`, `streaming_create_output`, `streaming_list_outputs`,
`streaming_get_output` and `streaming_stop_output` operations. Creation returns
observed idle/running/failed state, never implies capture started, and is not
retried automatically. Protocol schemas come from discovery; unavailable runtimes
remain visible. Output acquisition timestamps use decimal nanosecond strings.
The original 59-operation compatibility record remains historical evidence.

Regenerate reviewed schema changes with `npm run generate`, then `npm run build`,
`npm run coverage` and `npm test`. The output delta was checked against actual
FastAPI method/path/operation IDs without starting application lifespan; original
operation triples were retained. Only five paths and three component schemas were
added to the accepted OpenAPI snapshot. The current snapshot SHA-256 is recorded
separately from the baseline registered-route artifact hash.
