# UltraSkelly consumer handoff

This batch extends PR #932 on `sfn26-ultraskelly`, starting at
`d36e0ac79855d3048361a278cf0fae649d9d2330`. It preserves the original PR commits
and the existing wire format. It is a branch for consumer testing, not a merge
into `sfn26` or a published package release.

## What to use

The original PR supplies application-defined messages, image payload readers and
native JPEG helpers, a standalone browser bundle, plain-HTTP connection support,
and the optional Python producer package. This batch adds:

- `@freemocap/client/stream`, independent of the HTTP operation bindings.
- Overlay tracker identity and reconstructed instance identity.
- `subscribeToChannels` and `resolveChannelViews` for all declared numeric
  channels, including kinds without specialized resolved views.
- Fixed registration snapshots, disconnect-aware retries, independent ownership
  of copied ArrayBuffers, and strict image integer/metadata checks.
- Producer validation that rejects fractional integer fields and invalid sample
  status values instead of truncating or wrapping them.

Generic views preserve channel descriptors and owner identities. They do not
invent names for rows whose producer omitted them, convert coordinates, or infer
physical units. Known model-indexed channels can be interpreted with the model
carried in the same event. Custom producers must define their row semantics.

## Publication state and consumer build

The owner authorized committing and pushing this validated batch on the existing
`sfn26-ultraskelly` branch. The original PR commits remain intact. Use the branch
commit reported with delivery to identify the tested changes; this does not merge
the branch into `sfn26`.

Use a clean checkout of `sfn26-ultraskelly`; preserve any local work before
updating. From that branch, run `git pull --ff-only origin sfn26-ultraskelly`.

For the TypeScript package, from `packages/freemocap-client`:

```sh
npm ci --ignore-scripts
npm test
```

This builds ESM, declarations and `dist/browser/freemocap-client.js`. Point the
consumer's local package dependency or static asset copy at this checkout's
fresh build. The package version remains `0.1.0-dev.0`; record `git rev-parse HEAD`
alongside the consumer test, since that version alone does not identify the code.

For the Python producer, from `packages/freemocap-stream`:

```sh
uv sync --frozen --group dev
uv run --no-sync python -B -m pytest -q
```

Use this checkout's package in the consumer's chosen environment. Its dependency
set remains `cbor2` and `numpy`; it does not require the FreeMoCap server.

## Pair images and detections at the producer

Assign source frame identity at acquisition and keep it attached to the image
through inference. Assemble a frame using the image that produced its detections.
The outer `frame_number`, envelope `sequence`, and image payload's frame number
describe that source frame. Preserve acquisition time in `timestamp`; do not
replace it with inference completion or transmission time.

When inference lags, publish the matching older image with its results, or skip
that complete preview frame according to the application's delivery policy.
Attaching old detections to a newer image under the newer frame number creates a
false measurement association. Multi-camera grouping must preserve the producer's
actual synchronization and timing provenance; a shared group number does not
establish simultaneous capture.

Overlay callbacks precede the image callback for the same frame. Pair them using
the supplied frame number and camera ID; retain tracker/instance identities when
several subjects share a camera. Generic channel events provide the same source
frame number and timestamp. They do not require a metadata handshake.

## Consumer acceptance

On the actual UltraSkelly machine, check plain-HTTP connection, custom robot
state, camera decoding, and several tracked subjects. Confirm overlays retain
their declared identities when array order changes. Register one custom numeric
channel and inspect its descriptor and values. Disconnect during a connection
failure and confirm retries stop. Reconnect mid-stream and verify a frame renders
without earlier metadata. Report the branch commit, browser/runtime versions,
observed failures, and image-path timings separately from protocol timings.

The strict image reader rejects the entire malformed payload rather than
rendering a valid prefix. JPEG byte views share the input payload buffer;
`decodeImageBitmaps` returns bitmaps the caller must close. The numerical channel
views share decoder-owned storage and must be copied before transfer or mutation.

## Remaining work

Codec ownership consolidation, generated multilingual specifications, capability
discovery, renderer optimization, smaller validators, public package releases,
and community plugin loading remain separate decisions. No new promise of Core
producer extensibility follows from the client's generic channel view. The
original Pi measurements remain author-reported evidence; this batch does not
claim to repeat them or establish native browser JPEG acceptance.

## Validation of this local batch

On 2026-11-02, using isolated environments installed from the committed lockfiles:

- SDK `npm test`: 130 passed; 69 operation bindings checked; four examples passed
  syntax checks. Includes browser-bundle import/decoding in Node, generic channel
  subscriptions and reset, owner identity, buffer transfer, registration mutation,
  error/state callback disconnect, and malformed image metadata.
- UI `npm run test:sdk`: TypeScript passed; 96 tests passed and one optional
  reference-data case skipped; seven progress tests and both camera-control
  harnesses passed.
- Python producer: 45 passed, one module skipped. `test_conformance.py` could not
  import `freemocap.core.streaming.message_model` because Core is not installed in
  this small environment. This does not establish fresh byte conformance with
  Core and SkellyCam. The SDK's existing independent Python-output fixture passed.
- Bibliography: 74 references, zero errors; eight validator tests passed.
- Whitespace checks passed. Build outputs, environments and test logs are ignored
  and are not part of the source diff.

No live cameras, training, app restart, package publication, native browser JPEG
test or Raspberry Pi benchmark was performed. The first sandboxed Python test
process stalled without output and was stopped; the same isolated environment's
test run outside the sandbox passed.
