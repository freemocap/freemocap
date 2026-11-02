# FreeMoCap JavaScript/TypeScript client

`@freemocap/client` is a standalone ESM client for the accepted FreeMoCap server
contract. JavaScript and TypeScript use the same implementation. It provides all
65 supported HTTP operations, binary resources, task controls, the bidirectional
WebSocket, and recording decoding. It does not require React, Electron or Python.

Version `0.1.0-dev.0` is private and **not published to npm**. It targets the exact
server baseline in [compatibility](compatibility/0.1.0-dev.0.json), not every server
with the same application version or WebSocket shape version. See the
[operation coverage](contracts/coverage.md) and [contract sources](contracts/README.md).

## Install from source

From the FreeMoCap repository, change to `packages/freemocap-client`, run
`npm ci --ignore-scripts`, then `npm run build`.
In a consuming project, run `npm install /absolute/path/to/freemocap-client`.
The default app uses this package through a local file dependency within the same
repository. Package interfaces and tests remain independent of the application.
Node 22+ is declared; the compatibility record names the runtimes actually tested.
Browsers consume the ESM package through a bundler. There is no CommonJS or CDN build.

```js
import {createClient} from '@freemocap/client';

const client = createClient({baseUrl: 'http://127.0.0.1:8005'});
const {data: health} = await client.operations.healthcheck_endpoint_health_get();
console.log(health);
client.stream.subscribeToModelFrames(models => {
  // Each model has its own identity, ordered points and optional channels.
  for (const model of models) console.log(model.modelId, model.landmarks?.names);
});
client.stream.subscribeToProtocolErrors(console.error);
client.stream.connect();
// Later: client.close();
```

The address is a configuration value, not a discovery mechanism. The SDK neither
launches a server nor invents a playback-control endpoint. For HTTP-only consumers,
import `createHttpClient` from `@freemocap/client/http`.

## HTTP, resources and tasks

`operations` uses the server's OpenAPI operation IDs. TypeScript derives the
required path/query/body fields and response types from the reviewed schema.
HTTP JSON retains server field names; these bindings do not perform universal
runtime response-schema validation. Each call accepts the applicable
`{path, query, body, headers, signal, cache, keepalive}` and returns
`{status, headers, data}`. Missing optional query values are omitted.

`responses` takes the same typed inputs and returns the original, unconsumed
`Response`. The caller handles HTTP statuses and response validation on this surface.
The default app uses it to preserve existing validation and error presentation.

Video and Parquet `operations` return an unconsumed `Response` in `data`. Pass a
`Range` header when needed; status, content headers and byte ownership are preserved.
`asset(serverRelativeUrl)` returns the same wrapper, and `assetResponse` returns a
raw `Response`. Use URLs supplied by the server; a local filesystem path is not an
HTTP asset URL. Existing hidden utilities remain explicit:
`utilities.playbackViewer()` and `utilities.parquetByPath(serverAbsoluteParquetPath)`.

`operations` throws `ApiError` with `status`, `body`, `headers` and `url` for HTTP
errors. Network failures and aborts retain their original error. No HTTP command
is automatically retried. Supply `fetch` and default `headers` for injection.

A recording ID is a folder name; `recording_parent_directory` selects an alternate
parent. A run ID, recording revision, capture ID and task ID are different identities.
An export's 202 response means accepted. Poll its returned task ID or subscribe to
progress snapshots until a terminal status. HTTP abort does not cancel the task;
use the explicit task-cancel operation. Cancellation acceptance is not completion.
The export catalog can remain available after a task snapshot is retired, and its
filesystem paths are not automatically downloadable URLs.

## Streaming and ownership

The stream starts disconnected. It supports `frame`, `log`, `framerate`, `app_state`
and `progress`; raw validated messages and resolved frame/metadata subscriptions
are available. Progress uses `snapshot.server_instance_id` and `snapshot.revision`.
Do not treat default envelope counters as universal ordering or wall-clock guarantees.

Every frame carries its descriptors. Metadata identity reuse is an optimization,
never a decoding prerequisite. Unknown kinds/versions are skipped; malformed known
messages reach protocol-error subscribers. Subscriber exceptions are isolated.

The connection sends text ping/pong and can reconnect after unexpected closure.
`sendDisplayFeedback(frameNumber, sizes)` sends display hints, not a delivery gate.
Each connection has a fresh connection ID. `disconnect()` and `close()` stop the
socket/timers and clear decoder/resolver caches; reset subscribers receive empty
state. HTTP requests and server tasks are not cancelled by `close()`.

Treat received numerical/image bytes as read-only. Copy before editing or
transferring their buffers. Later frames do not overwrite retained arrays.
Coordinates, units, names, channel order and clocks keep their declared meaning.
No implicit coordinate conversion or fabricated samples are applied.

A custom `socketFactory` must implement the browser WebSocket event/property
interface. HTTP default headers do not become WebSocket upgrade headers; browser
WebSockets use the browser's authentication facilities.

### Streams from other applications

Another server can reuse this stream: construct `TransportService` with its socket
URL and register the application's own message kinds. Each kind gets a parser (a Zod
schema works) and an optional `version` (default 0). Its messages carry the standard
envelope (`kind`, `version`, `timestamp`, `sequence`) and stay self-describing.

```ts
import {TransportService} from '@freemocap/client';
import {z} from 'zod';

const RobotState = z.object({kind: z.literal('robot_state'), version: z.literal(0),
  timestamp: z.number(), sequence: z.number().int(), servos: z.record(z.string(), z.number())});
const stream = new TransportService({url: 'ws://robot.local:8080/ws', kinds: {robot_state: RobotState}});
stream.subscribeToKind('robot_state', state => console.log(state.servos));
stream.connect();
```

Application messages reach `subscribeToKind` only, never `subscribeToMessages`.
FreeMoCap's kinds cannot be redefined; a server that sends `frame` messages gets the
usual frame, image and overlay subscriptions. Unregistered kinds and other versions
are skipped, and malformed registered messages reach protocol-error subscribers.

## Recorded data

```js
import {PlaybackManifestSchema, decodeRecordingParquet} from '@freemocap/client/recording';
const input = {path: {recording_id: 'trial'}, query: {recording_parent_directory: 'C:/recordings'}};
const manifest = PlaybackManifestSchema.parse(
  (await client.operations.recordings_get_playback_manifest(input)).data);
const {data: response} = await client.operations.recordings_get_recording_parquet(input);
const runs = await decodeRecordingParquet(await response.arrayBuffer(), manifest);
console.log(runs[manifest.selected_run_id]);
```

The generic reader returns all declared dynamic channels with dense `Float64Array`
values, names, component units/order, stage provenance, source clocks and frame
numbers. Missing values remain `NaN`. Static channels remain in the manifest.
`selectChannel` can limit decoding allocations. The default application's
`decodePlaybackParquet` preserves its existing scene-channel selection.
Presentation helpers create float32 views without changing the float64 source.
Play, pause and seek belong to the consuming application.

## Runnable examples

After building, run from this checkout:

```sh
node examples/inspect-server.mjs http://127.0.0.1:8005
node examples/stream.mjs http://127.0.0.1:8005 10
node examples/recording.mjs http://127.0.0.1:8005 trial C:/recordings
node examples/export.mjs http://127.0.0.1:8005 trial C:/recordings
```

The first three inspect/receive existing data. The export example explicitly
creates a server-side NPZ export and waits for its task. None starts cameras.
The examples retain generic model/channel names and do not require a renderer.

## Development and acceptance

`npm run generate` reads the reviewed local OpenAPI snapshot. Binary-response
overrides trace actual server handlers because inferred OpenAPI does not describe
those bytes. `npm test` builds, checks negative TypeScript cases and runs independent
HTTP/decoder/socket/recording tests. `npm run coverage:check` verifies the documented
65-operation inventory against the generated bindings. `npm run examples:check`
checks example syntax; real example execution is a separate owned-server gate.

Core provides `python -m freemocap.tools.sdk_validation`, `sdk_replay_validation`,
`sdk_live_validation` and `sdk_examples_validation` for integration acceptance.
Use their `--help`; choose new ignored output directories. Live validation requires
an exclusive camera/GPU slot. Tests use private recording copies and verify cleanup.
The compatibility record distinguishes synthetic coverage, recorded-channel socket
replay, real capture, production-app observation and untested external integrations.
