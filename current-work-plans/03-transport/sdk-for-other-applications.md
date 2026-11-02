# Reusing the stream from another application

Branch `sfn26-ultraskelly`, started from `sfn26` at `2c9252c9`. Status on
2026-11-02: implemented and tested on the branch, and used by UltraSkelly's `main`
([freemocap/ultraskelly](https://github.com/freemocap/ultraskelly)). Not merged
into `sfn26`; nothing published.

## Why

UltraSkelly is an animatronic skeleton driven by a Raspberry Pi 5. Its dashboard
needs what FreeMoCap's browser already gets: live camera video with the detected
keypoints drawn over it, plus the robot's own state, streamed from a Python server
to browsers on the local network. Its server differs from FreeMoCap's in every
other way: aiohttp instead of FastAPI, Python 3.13 on a Pi, its own endpoints, one
uncalibrated camera, YOLOv8 keypoints from a Hailo-8, and no 3D model.

The adaptation keeps FreeMoCap's transport exactly: one WebSocket of
self-describing CBOR messages ([message-protocol.md](message-protocol.md)), each
interpretable on its own, delivered newest-first. No new framing, metadata
deltas or handshakes were introduced. UltraSkelly's video uses the `frame` kind
unchanged; its robot state is a new application kind with the standard envelope.

## What the adaptation needed and what changed

| Need | Gap on `sfn26` | Change on this branch | Evidence |
| --- | --- | --- | --- |
| The application's own messages | `TransportService` and `parseMessage` accept only `frame`, `log`, `framerate`, `app_state` and `progress`; anything else is skipped | `new TransportService({url, kinds})` registers application kinds with any parser (a Zod schema works) and an optional version; `subscribeToKind` delivers them, typed. They keep the envelope and fail soft or loud like FreeMoCap kinds, and FreeMoCap kinds cannot be redefined (`e1f0918a`) | `tests/application-kinds.test.mjs`, type checks in `tests/types.ts` |
| Video in the browser | Reading SkellyCam's image payload and decoding its JPEGs lived in `freemocap-ui`; SDK users received opaque bytes | `@freemocap/client/images`: `readImagePayload` (strict, like SkellyCam's own validation decoder) plus `decodeImageBitmaps` and `decodeImagePixels`. The UI's parser is now a thin wrapper, its JPEG decoder a re-export, and its copy of the layout is gone (`5e5e27af`) | Fixture written by SkellyCam's `encode_image_payload`; UI `test:sdk` and Vite build pass (decode worker 4 kB) |
| Pages without a bundler | ESM output with bare `cbor-x` and `zod` imports | `npm run build` also writes `dist/browser/freemocap-client.js`, one minified module with a source map, exported as `@freemocap/client/browser` (`e56605be`) | `tests/browser-bundle.test.mjs`; `tests/browser/bundle-check.html` passes in Chromium |
| Dashboards on other computers | `WebSocketConnection` called `crypto.randomUUID`, which exists only in secure contexts [@mdnCryptoRandomUUID]. On a page served over plain HTTP from a LAN address the call threw inside `connect()`, which retried silently forever | `randomId()` falls back to `getRandomValues`, available in insecure contexts [@mdnCryptoGetRandomValues], setting the version 4 and variant bits [@rfc9562]. A socket that cannot be created is now reported on the `error` event (`342c34b7`) | Two tests in `tests/socket.test.mjs`; UltraSkelly's dashboard from another computer |
| A Python server outside FreeMoCap | Encoding lives in Core (`message_model.py`, importing Core, SkellyForge and SkellyCam) and SkellyCam (`frontend_payload_bytearray.py`, needing OpenCV and pydantic); the relay and single writer are Starlette-specific | `packages/freemocap-stream`, depending on `cbor2` and `numpy` only: envelopes, frame helpers (uncalibrated cameras, `OVERLAY_2D` channel blocks, connection groups, tracker observations), an image payload writer for already-encoded JPEGs, and `Latest` plus `StreamConnection` for newest-wins delivery through one writer, with `ping` answered (`b1ac25be`, `1cf8e895`, `fc8364c4`) | Byte-identical to Core's `encode_message` and SkellyCam's `encode_image_payload`; `tests/python-stream.test.mjs` decodes the package's output through `TransportService` |
| Windows checkouts | `coverage:check` compared CRLF-checked-out text with LF output | The check ignores line endings (`4fc2e8a2`) | SDK suite passes on Windows |

## How UltraSkelly uses it

The Pi publishes one `Latest` per camera and one for state. Each frame message
carries the OAK image and the keypoints the detector found in that same image
(the detector's pose message references its source frame), one `OVERLAY_2D`
tracker observation per person with `model_id` null and a COCO connection
group. `robot_state` messages carry motor commands, target, rates and node
health at 20 Hz. The browser loads the vendored bundle, registers `robot_state`,
and draws each image with its overlays: overlays for a frame arrive just before
its image.

## Measurements

On the Pi 5 with Chromium 156, both viewers received about 30 frames per second
and 19 `robot_state` messages per second. Replaying 120 captured frame messages
(33 KiB each) through the SDK in the Pi's Chromium, per frame:

| Stage | Time |
| --- | --- |
| CBOR decode and validation | 0.13 ms |
| Full `TransportService` dispatch, overlays resolved | 0.08 ms |
| JPEG to `ImageBitmap` (wall time) | 2.59 ms |
| Canvas draw | 0.82 ms |

The SDK's message handling is negligible: about 2.7% of a core on the main
thread at 30 frames per second. Against UltraSkelly's previous MJPEG `<img>`
video, the Pi's Chromium used about a fifth of a core more (107% versus 83% with
one viewer). That difference is the image path: decoding each JPEG, drawing it
and compositing the canvas.

## Recommendations

The integration review, [sdk-external-review.md](sdk-external-review.md), ranks these
findings and expands them into a wish list for the multi-language and plugin work.

1. **Merge the branch's changes into `sfn26` after review.** They are additive:
   FreeMoCap kinds, decoding and UI behavior are unchanged, except that the image
   reader now rejects a malformed payload instead of rendering its valid prefix.
2. **Lower image cost on small displays before touching validation.** Other
   servers can honor the display-size feedback the client already sends
   (`sendDisplayFeedback`) and scale JPEGs down, as FreeMoCap's server does.
   An optional worker, `OffscreenCanvas` or WebCodecs renderer in the SDK could
   take decoding and drawing off the main thread; measure on the Pi first.
3. **Shrink the browser bundle.** Zod is 310 KB of its 380 KB (84 KB gzipped).
   Validation costs almost nothing at runtime, so this is only download size; a
   lighter validator for the browser build, such as Zod Mini, would cut it.
4. **Give overlays their identity.** `OverlayFrame` drops the tracker ID, so the
   people in one frame are distinguishable only by order. Exposing the tracker
   or instance ID would let viewers keep colors stable per person.
5. **Keep one owner per encoding.** SkellyCam could export a pure packer for
   already-encoded JPEGs, and Core could build its envelope, channel and image
   encoding on `freemocap-stream`. Until then the conformance tests guard both.
6. **Name the two image-size orders.** On the wire, `image_size` is (width,
   height): `websocket_server.py:134`, `outputs/source.py:30`, `CameraModel`
   (`camera_model.py:20`), read that way by the UI
   (`ServerContextProvider.tsx:124`). Inside, observation series use numpy's
   (height, width) under the same name: `recording_processing.py:64`,
   `saved_observations.py:68`, `observation_publication.py:109`, flipped at
   `live_matching.py:63`. This is consistent today but easy to break; rename the
   internal field, for example `image_shape`.
7. **Document frame identity for render-complete frames.** A server pairing
   images with detections needs the detector to report which frame it used;
   UltraSkelly added that to its own messages. A short note in the protocol docs
   would save the next application the same discovery.

## Not verified

Playwright and native UI cases were not run. Node 23.8 and Chromium 156 were the
only runtimes exercised, and the Python package was tested on Python 3.12 (Core's
environment) and 3.13. The image-reader behavior change has no UI test.

Validation on the branch head: SDK `npm test` 120 passed; UI `npm run test:sdk`
95 passed and 1 skipped (reference data not configured) plus 7 passed; UI Vite
build passed; `freemocap-stream` 27 passed and 1 skipped alone, and 29 passed in
Core's environment, conformance included.
