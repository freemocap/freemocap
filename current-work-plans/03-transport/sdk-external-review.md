# External integration review: the stream and `@freemocap/client`

Review date 2026-11-02. Baseline: `sfn26` at `ef385100`, merged into branch
`sfn26-ultraskelly`. Audience: owners of the client SDKs (TypeScript now, Python
and Rust next), the producer side, and the planned plugin system. Companion
document: [sdk-for-other-applications.md](sdk-for-other-applications.md), which
lists every change on the branch with its evidence.

## Summary

This was the first use of the stream and the client SDK by an application outside
FreeMoCap. The wire protocol needed no changes: every requirement fit the
existing `frame` message plus one application-defined message kind. The SDK, on
the other hand, was packaged as FreeMoCap's own client. The integrating
application hit six gaps before its first frame rendered, and one of them failed
silently. The branch closes those gaps with additive changes. This review ranks
what remains and turns the experience into requests for the multi-language and
plugin work.

## Integration context

| Aspect | Integrating application |
| --- | --- |
| Producer | aiohttp server on a Raspberry Pi 5, Python 3.13, a USB camera, YOLOv8 pose on a Hailo-8 |
| Consumers | Chromium 156: a full-screen window on the Pi and browsers on the local network over plain HTTP |
| Stream content | One camera at 640×480 and 30 fps; 2D keypoints for every detected person (no calibration, no 3D model); a robot-state message at 20 Hz |
| SDK parts used | `TransportService`, CBOR decoding and validation, overlay resolution with detector connection groups, the SkellyCam image payload, and the new application kinds, image decoders and browser build |
| SDK parts unused | The HTTP operation bindings, recording readers and 3D model frames |

## What worked and should be kept

- **Self-describing messages.** Late joiners and reconnects needed no handshake
  and no special handling. This is the protocol's strongest property; keep it in
  every language.
- **Newest-wins delivery.** A slow viewer receives fewer, newer frames, and the
  producer never queues.
- **An expressive frame contract.** An uncalibrated camera, per-person 2D
  keypoints and detector-owned connection groups fit without inventing anything.
  The change making tracker `model_id` nullable arrived exactly when needed.
- **Clear failure semantics.** Unknown kinds and versions are skipped; malformed
  known messages throw to protocol-error subscribers; one subscriber's exception
  cannot break fan-out.
- **Useful ordering.** A frame's overlays are delivered just before its image,
  so a consumer pairs them by frame number without buffering.
- **Testing culture.** Fixtures written by independent encoders made
  byte-for-byte conformance between producers a test rather than an assumption.

## Findings

| # | Finding | Impact | Status on this branch |
| --- | --- | --- | --- |
| 1 | Connections from pages served over plain HTTP fail silently | Critical | Fixed (`342c34b7`) |
| 2 | Unknown message kinds are dropped with no extension point | High | Fixed (`e1f0918a`) |
| 3 | Image payload decoding lived in the FreeMoCap UI, not the SDK | High | Fixed (`5e5e27af`) |
| 4 | No producer kit outside Core | High | Added `freemocap-stream` (`b1ac25be`, `1cf8e895`, `fc8364c4`) |
| 5 | No distribution for pages without a bundler | Medium | Fixed (`e56605be`) |
| 6 | How a producer pairs detections with their image is undocumented | Medium | Documented in the [handoff](ultraskelly-consumer-handoff.md) (`f729e8ae`) |
| 7 | Overlay frames drop the tracker's identity | Medium | Fixed (`f729e8ae`); consumer-verified in the [report](ultraskelly-consumer-report.md) |
| 8 | Image decoding and drawing dominate client cost | Medium | Open |
| 9 | Each wire encoding has more than one implementation | Medium | Open, guarded by conformance tests |
| 10 | Channels of unrecognized kinds pass validation but no resolved view exposes them | Medium | Fixed (`f729e8ae`); consumer-verified in the [report](ultraskelly-consumer-report.md) |
| 11 | The validator is 82% of the browser bundle | Low | Open |
| 12 | `image_size` uses two orders under one name inside Core | Low | Open |
| 13 | The coverage check failed on Windows checkouts | Low | Fixed (`4fc2e8a2`) |

1. **Silent failure on plain HTTP.** `WebSocketConnection` called
   `crypto.randomUUID()`, which browsers provide only in secure contexts
   [@mdnCryptoRandomUUID]. On a page served from a LAN address, the call threw
   inside `connect()`, the catch scheduled a retry, and the client cycled through
   reconnect states forever with no error. FreeMoCap's own app never meets this
   because it runs on localhost. Fixed with a `getRandomValues` fallback
   [@mdnCryptoGetRandomValues] that sets the version 4 bits [@rfc9562], plus an
   `error` event when a socket cannot be created. The lesson generalizes: a retry
   loop must never hide the reason it is retrying.
2. **No extension point for messages.** `parseMessage` accepted exactly five
   kinds. Any application state had to be squeezed into FreeMoCap's kinds or sent
   on a second socket. Now `new TransportService({url, kinds})` registers
   application kinds with any parser, a Zod schema included. They keep the
   envelope and the skip-or-throw semantics, `subscribeToKind` is typed, and
   FreeMoCap's kinds cannot be redefined.
3. **Video decoding outside the SDK.** The SDK handed consumers opaque bytes;
   reading SkellyCam's layout and decoding the JPEGs lived in the UI.
   `@freemocap/client/images` now owns both. Its reader is strict, as SkellyCam's
   own validation decoder is, so a malformed payload is rejected instead of
   partly rendered; that is the branch's one behavior change for the UI.
4. **No producer kit.** Producing a valid stream required Core's
   `message_model.py`, which imports Core, SkellyForge and SkellyCam, and
   SkellyCam's image packer, which needs OpenCV and pydantic. The relay and its
   single writer are Starlette-specific. `packages/freemocap-stream` depends only
   on `cbor2` and `numpy` and produces byte-identical output, which its
   conformance tests check against both originals.
5. **No bundler-free build.** The ESM output imported `cbor-x` and `zod` by bare
   name. `npm run build` now also writes one minified module with a source map.
6. **Pairing detections with images.** A render-complete frame needs the image
   and the detections made from that image. The integrating application had to
   add a frame identity to its own detector messages to achieve this. Nothing in
   the protocol documents tells a producer it must.
7. **Overlay identity.** `OverlayFrame` carries no tracker or instance ID, so the
   people in one frame are distinguishable only by order. Stable per-person
   colors or labels are impossible.
8. **Client cost is the image path.** Measured below: message handling is
   negligible, while JPEG decoding and drawing cost a low-power display about a
   fifth of a core more than native MJPEG.
9. **Encodings with several implementations.** The envelope and frame encoding
   exist in Core and `freemocap-stream`; the image layout in SkellyCam,
   `freemocap-stream` and the TypeScript reader. Conformance tests hold them
   together, but each change now has to be made in several places.
10. **Unrecognized channel kinds.** The resolver matches channels against a
    fixed list of kinds. A plugin's new channel validates, since `kind` is any
    string, but appears only in raw messages and never in resolved views.
11. **Bundle size.** The browser build is 380 KB, 84 KB gzipped; Zod is 310 KB of
    it. Validation is fast, so this concerns download size only.
12. **Two `image_size` orders.** The wire uses (width, height) everywhere.
    Core's internal observation series use numpy's (height, width) under the same
    name and convert at the boundary. Consistent today, easy to break tomorrow.

## Performance

Raspberry Pi 5 with Chromium 156, 640×480 JPEG frames of about 33 KiB, replaying
120 captured frame messages through the SDK:

| Stage | Per frame |
| --- | --- |
| CBOR decode and validation | 0.13 ms |
| Full `TransportService` dispatch with overlays resolved | 0.08 ms |
| JPEG to `ImageBitmap` (wall time) | 2.59 ms |
| Canvas draw | 0.82 ms |

Message handling uses about 2.7% of a core on the main thread at 30 frames per
second. Live delivery held 29-30 frames per second to two viewers with 19 state
messages per second. Compared with the application's previous MJPEG video, the
Pi's browser used about a fifth of a core more and the producer about 4% of a
core more.

## Wish list

Ordered by how much each item would have shortened this integration. Every item
keeps the transport fully self-describing: no handshakes, metadata deltas or
state-dependent decoding.

### For every client language

1. **One machine-readable stream specification.** Describe the envelope, every
   kind, the frame contract, channel blocks and the image payload layout once,
   for example in CDDL [@rfc8610]. Generate or check each language's types from
   it, so Python and Rust start from the contract rather than from the
   TypeScript code.
2. **A shared conformance corpus.** Golden messages from each encoder, Core,
   SkellyCam and `freemocap-stream`, paired with expected decoded values,
   extending the table in `shared/server-contract`. Include unknown kinds,
   unsupported versions, malformed messages, NaN values, empty trackers,
   multi-camera payloads and application kinds. Every client and producer passes
   the same corpus.
3. **A stream client separate from the FreeMoCap HTTP surface.** Connection,
   decoding and kinds should be usable without the application's operation
   bindings, in each language, with the FreeMoCap profile layered on top.
4. **Observable failures.** A typed connection state and error events; retries
   announce why they retry. No language should ship a silent retry loop.
5. **Typed application kinds everywhere.** TypeScript generics exist now. Python
   could use dataclasses or pydantic models, and Rust serde enums.

### For producers and the plugin system

6. **One owner per encoding.** SkellyCam exports a packer for already-encoded
   JPEGs without OpenCV; Core encodes through `freemocap-stream`; producer kits
   in other languages come from the specification.
7. **Namespaced kinds for plugins.** For example `<namespace>.<kind>`, with
   FreeMoCap's kinds reserved and rules for collisions and versions per kind.
8. **A path for plugin channels.** State that unrecognized channel kinds are
   valid, and give clients a generic resolved view of any channel (names,
   columns and a Float32 view), so a plugin can add data without a client
   release.
9. **Optional capability description.** A replace-kind message, like
   `app_state`, saying which kinds and channels a producer emits, so generic
   viewers can build their interface. Informational only: decoding must never
   depend on it.
10. **Frame identity guidance.** Document how producers pair detections with
    their source image, and which fields carry the frame number and source time.
11. **Display-size feedback in producer kits.** Clients already send display
    sizes; a producer helper that scales each client's JPEGs would cut cost on
    small displays.

### For client ergonomics

12. **An off-main-thread renderer.** A worker, `OffscreenCanvas` or WebCodecs
    helper that decodes and draws camera images, measured on low-power devices.
13. **Overlay identity.** Expose the tracker or instance ID on `OverlayFrame`.
14. **A smaller browser build.** A lighter validator for the browser bundle, such
    as Zod Mini, or generated validators.

### For packaging and release

15. **Published packages with versions.** npm, PyPI and crates.io releases with
    compatibility records. Until then, document installs from Git; the Python
    package's README does.
16. **Browser tests in SDK CI.** JPEG decoding and the bundle can only be tested
    in a browser; the branch adds a manual check page.
17. **Per-language quick starts** for using the stream from another application,
    without hardcoded counts that go stale.

## Evidence

On the merged branch: SDK `npm test` 120 passed; UI `npm run test:sdk` 96 passed
and 1 skipped (reference data not configured) plus 7 passed; `freemocap-stream`
27 passed and 1 skipped alone, and 29 passed in Core's environment with byte
conformance against Core and SkellyCam. The integrating application ran on the
branch's packages on Raspberry Pi hardware. Not exercised: Playwright and native
UI cases, Firefox and Safari, and Node versions other than 23.8.
