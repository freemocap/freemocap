# UltraSkelly consumer report

Report date 2026-11-02. This answers the [consumer handoff](ultraskelly-consumer-handoff.md):
UltraSkelly moved to the batch, adopted its new contracts, and ran the consumer
acceptance checks on the robot's Raspberry Pi. Every applicable check passed and no SDK
failure was observed.

## What was tested

| Item | Identity |
| --- | --- |
| SDK under test | `sfn26-ultraskelly` at `f729e8aeaba495839d7372c2f20c18c96618f4f6`, version `0.1.0-dev.0` |
| Producer | `freemocap-stream` from that commit, pinned in UltraSkelly's `uv.lock` |
| Browser client | the `dist/browser/freemocap-client.js` bundle built from that commit (382,960 bytes, 84,779 gzipped), vendored without a bundler |
| Application | UltraSkelly branch `wip/w6-sdk-521485` at `199f95d` for the robot run; the SDK pin is on UltraSkelly's `main` as `0a5296a` |
| Branch head now | `08239336` merges `sfn26` at `f4c38bbf`; see [Validation](#validation) for its tests |

The merge changes no stream code UltraSkelly uses. The producer package is identical.
The client gains an optional `object_geometry` in model definitions, new HTTP operation
bindings, and citation keys in a comment; the browser bundle grows to 383,838 bytes.
UltraSkelly stays pinned to the tested commit.

### Environment

| | |
| --- | --- |
| Machine | Raspberry Pi 5 Model B Rev 1.1, Debian 13 (trixie), kernel 6.18.50+rpt-rpi-2712 |
| Producer runtime | Python 3.13.5, cbor2 6.2.0.post2, numpy 2.3.4, aiohttp 3.14.5 |
| Robot | OAK-1 at 640×480 and 30 fps (depthai 3.11.0), YOLOv8 pose on a Hailo-8 (HailoRT 4.23.0), motors simulated |
| Browser | Chromium 156.0.8078.73, headless (`--headless=new`), on the Pi |
| Page | served over plain HTTP from the Pi's LAN address, so not a secure context: `crypto.randomUUID` is undefined |
| Bundle build | Node 23.8.0, npm 11.19.0 on Windows 11 |

A dry run of the same checks in headless Chrome 156.0.8078.79 on a Windows PC also passed.

## What UltraSkelly adopted

- **Pairing at the producer.** Frames already traveled with the detections made from
  them. Each pose message now also carries the target the controllers received from the
  same detections, and the row of the person it belongs to.
- **Declared identities.** Each person's observation has `detector_type` `yolov8_pose`
  and `tracker_id` `target` for the person the head follows, or `person-<row>` for the
  others (best score first). YOLOv8 pose has no temporal tracking, so these IDs name roles
  in one frame: as the handoff says, they state what the producer declared and create no
  tracking over time. Consumers find people by `trackerId`, never by array position.
- **A custom numeric channel.** The followed person also carries `ultraskelly.target`:
  columns `x`, `y` (pixels of `image_size`) and `body_angle_deg`, one row named `target`,
  with `camera_id` and `image_size`. Read with `subscribeToChannels`, it lets a viewer
  stop drawing the unpaired 20 Hz `robot_state.target` over video, which put a target
  from one moment over an image from another; UltraSkelly's dashboard rebuild adopts it.
- **Ownership rules.** UltraSkelly's stream guide now tells its viewers to close every
  bitmap from `decodeImageBitmaps` and to copy JPEG and channel views before modifying or
  transferring them. The existing dashboard already did both.
- **Producer validation.** No changes needed: UltraSkelly's frame numbers, camera indices
  and sizes were already non-negative integers.

UltraSkelly's [stream guide](https://github.com/freemocap/ultraskelly/blob/6b935ea29a6d9cd4494eccda09e87432bb28b7b9/docs/stream.md)
documents every field it sends.

## Consumer acceptance

The checks ran as a page in Chromium, driven by
[`scripts/stream_acceptance.py`](https://github.com/freemocap/ultraskelly/blob/6b935ea29a6d9cd4494eccda09e87432bb28b7b9/scripts/stream_acceptance.py)
over the DevTools protocol, against two producers:

- **Synthetic:** UltraSkelly's real producer code fed by a synthetic camera
  (`python -m ultraskelly.replay --serve --people 3`): three people at 30 fps whose row
  order is shuffled every frame, the middle one followed.
- **Robot:** the bot with the OAK and the Hailo-8, motors simulated. Nobody was in view,
  so the checks that need people apply only to the synthetic run.

| Check | Synthetic | Robot | Evidence |
| --- | --- | --- | --- |
| Plain-HTTP connection | Pass | Pass | Connected from a page that is not a secure context |
| Custom robot state | Pass | Pass | `robot_state` registered with a parser: 18.6 and 19.1 messages/s |
| Camera decoding | Pass | Pass | 30.2 and 30.1 frames/s decoded and drawn, every bitmap closed; OAK JPEGs 29 KB |
| Several tracked subjects | Pass | n/a | 3 people in every frame |
| Identities when array order changes | Pass | n/a | 303 of 303 frames: the overlay declared `target` was the person the target channel points at, and the middle person, while their row moved through 0, 1 and 2 |
| One custom numeric channel | Pass | n/a | `ultraskelly.target`, owner `{scope: 'tracker', trackerId: 'target', modelId: null}`, columns `x,y,body_angle_deg`, names `['target']`, 1 row, values such as `[339, 150, -90]` |
| Retries stop after disconnect during a connection failure | Pass | Pass | Port 1 refused; disconnecting on `error` or on the `RECONNECTING` state change left 1 attempt and `DISCONNECTED` after 6.5 s |
| Mid-stream reconnect renders without earlier metadata | Pass | Pass | After `disconnect()` the same service redrew in 42 and 36 ms, and channel subscribers received `null`; a new service drew its first frame in 9.4 and 13.1 ms |

No protocol errors, console messages or image errors occurred in either run.

## Timings

Captured frame messages were replayed one at a time after the live checks: 120 frames
from each producer, plus the `robot_state` messages captured with them. Without
cross-origin isolation the page's clock ticks in about 0.1 ms steps, so the protocol
steps and the payload read are averages over all 120 frames (median of five runs);
JPEG decoding and drawing are per frame. JPEG decoding is the wall time of
`decodeImageBitmaps`. Drawing ends with a one-pixel read so the canvas work is
included. Headless Chromium had no GPU context on the Pi (see below), so its canvas
work ran without GPU acceleration.

| Per frame, ms | Synthetic (25.8 KB, 3 people, 4 channels) | Robot (29.9 KB, no people) |
| --- | --- | --- |
| **Protocol:** CBOR decode and validation (`MessageDecoder`) | 0.124 | 0.065 |
| Frame resolution (`FrameResolver`) | 0.004 | 0.001 |
| Channel views (`resolveChannelViews`) | 0.002 | 0.001 |
| `robot_state` CBOR decode, per message | 0.028 | 0.032 |
| **Image path:** payload read (`readImagePayload`) | 0.007 | 0.005 |
| JPEG decode, median (p95) | 2.3 (3.2) | 2.9 (4.3) |
| Draw, median (p95) | 0.6 (1.0) | 0.4 (0.9) |

The image path costs 20 to 50 times the protocol. These figures match the earlier
measurement on `342c34b7`, taken in the Pi's full-screen Chromium: 0.13 ms for decoding
and validation, 2.59 ms for JPEG decoding and 0.82 ms for drawing (see the
[external review](sdk-external-review.md)). Message handling stays negligible; the
renderer optimization listed under remaining work is still where client time goes.

## Observed failures

None in the SDK. Two environment problems are worth knowing for browser tests on
desktop machines:

- Chromium started inside a desktop session without `--password-store=basic` asked for
  the keyring password on the robot's screen and stalled the headless check. The driver
  now always uses a throwaway profile, `--password-store=basic` and `--no-proxy-server`.
- Headless Chromium on the Pi had no WebGL by default ("BindToCurrentSequence failed").
  UltraSkelly's dashboard needs WebGL for its 3D view and ran with
  `--use-angle=swiftshader --enable-unsafe-swiftshader`; the acceptance page uses only a
  2D canvas.

Not exercised: people in front of the robot's camera, Firefox and Safari, GPU-drawn
Chromium windows, and the SDK's native JPEG path in Node.

## Next wishes

In order of what would help UltraSkelly most:

1. **Retry and heartbeat options on `TransportService`.** `WebSocketConnection` accepts
   `reconnectDelay` and `heartbeatInterval`, but `TransportService` constructs it with
   neither, so stream consumers always wait 5 s to retry. The retry check above has to
   wait 6.5 s.
2. **Renderer optimization.** JPEG decoding is 2.3 to 2.9 ms of every frame on the Pi; a
   worker or WebCodecs path measured on low-power devices remains the largest client
   win.
3. **Browser checks in SDK CI.** The UltraSkelly page and driver are small and run in
   headless Chromium; adapted to a fixture producer, they could cover JPEG decoding and
   the bundle, which Node tests cannot.
4. **Guidance on tracker identity over time.** Say whether `tracker_id` is expected to
   be stable across frames. Detectors without tracking, like UltraSkelly's, can only
   declare per-frame roles; a viewer cannot tell those apart from stable track IDs.
5. **A stream-only browser bundle.** `@freemocap/client/stream` exists for bundlers, but
   pages without one get the full bundle, HTTP operation bindings included.
6. **Application-kind decoding outside `TransportService`.** `MessageDecoder` returns
   `null` for application kinds, so recorders and test tools need their own CBOR decoder
   to read them.

## Validation

| Suite | `f729e8ae` | `08239336` (merge) |
| --- | --- | --- |
| SDK `npm test` | 130 passed; 69 bindings; 4 examples | 135 passed; 74 bindings; 4 examples |
| `freemocap-stream` pytest | 45 passed, 1 skipped | 45 passed, 1 skipped (package unchanged) |
| UI `npm run test:sdk` | not rerun | TypeScript passed; 126 passed, 1 skipped; 7 progress tests and both camera harnesses passed |
| Bibliography | not rerun | 74 references, 0 errors; 8 validator tests passed |
| UltraSkelly suite at `6b935ea` | 119 passed, 7 skipped (Windows; OpenCV and POSIX-only tests skip); 130 passed (Pi) | not rerun; UltraSkelly stays on `f729e8ae` |

The merge kept this branch's client contracts and tests and took `sfn26`'s versions of
the UI's frame parser, which drops JPEG views before frames reach the camera workers, and
of the citation keys in `websocket-connection.ts`.

