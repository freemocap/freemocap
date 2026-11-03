# Streaming stereo and depth from another application

Report date 2026-11-02, updated 2026-11-03 with the dashboard's depth views. UltraSkelly, the animatronic skeleton that already reuses this
stream ([sdk-for-other-applications.md](sdk-for-other-applications.md)), added a ZED Mini
stereo camera in the skull's eye sockets. Its Raspberry Pi 5 streams both eyes, computes
depth from them and streams the depth for 3D views: a point cloud and mesh placed on the
skeleton's head. This note records what the SDK carried as it is, what it could not, and
what would help the next application that streams depth or RGB-D.

## What UltraSkelly sends

| Message | Rate | Contents |
| --- | --- | --- |
| `frame`, cameras `zed_left` and `zed_right` | 30/s | Both raw eyes (672×376 each) as one image payload |
| `frame`, cameras `zed_rectified` and `zed_depth` | up to 10/s | The rectified left eye, and depth drawn in colour, for video panels |
| `depth_frame` (application kind, version 0) | the same depth frames | uint16 millimetre depth (zlib), the rectified left JPEG, pinhole intrinsics, camera axes and the camera's pose in the robot's head frame |

UltraSkelly's [depth message page](https://github.com/freemocap/ultraskelly/blob/9fd36ce/docs/depth-stream.md)
specifies `depth_frame` field by field, with a browser decoding example; its
[stream guide](https://github.com/freemocap/ultraskelly/blob/9fd36ce/docs/stream.md) places it
among the other messages.

Measured on the Pi with the OAK, pose, the ZED and depth all running, motors simulated:
the bot used 95% of one core, pose held 30 fps, the stereo pair 29.6/s, and `depth_frame`
arrived 9.9 times a second at about 22 KiB each. Depth is OpenCV's semi-global matcher on
the CPU at 336×188: 17 ms a frame. The Hailo-8's StereoNet took 207 ms a frame and held
the chip, so pose fell to 25 fps at one depth frame a second; UltraSkelly keeps it off by
default. Details: UltraSkelly's [audit](https://github.com/freemocap/ultraskelly/blob/9fd36ce/docs/audit-2026.md).

## What worked as it is

- **A stereo pair is one frame.** The image payload already holds several cameras with one
  frame number, so both eyes travel together and a viewer never pairs a left image with
  the wrong right one. Each eye is an ordinary camera entry; panels appear with no change.
- **Depth as an application kind.** `encode_message` takes byte strings, the envelope
  stays standard, and `new TransportService({url, kinds})` delivers the message with its
  bytes as `Uint8Array`. Each message is complete, so a viewer that joins mid-stream draws
  the next depth frame at once: the transport stays self-describing.
- **Compression without a library.** Python's `zlib.compress` writes the zlib format, with
  its header and trailer [@pythonZlibModule]; browsers inflate it with the built-in
  `DecompressionStream('deflate')` [@mdnDecompressionStream], which the Compression
  standard defines as exactly that format [@whatwgCompressionStreams]. At level 1, 336×188
  depth took 1.3 ms on the Pi and about 15 KB; level 6 saved 8% for three times the time.

## What the SDK could not carry

1. **Lossless 16-bit images.** The image payload holds JPEGs only (`jpeg_string_length` in
   SkellyCam's layout), and JPEG cannot carry millimetre depth exactly. UltraSkelly sends
   depth in its own message kind, so every depth producer would invent its own. A frame
   could instead carry a depth block beside its image payload, self-describing like the
   rest: camera ID, width, height, dtype, units, the value meaning "unknown", byte order,
   compression and the bytes, with a client helper that returns a typed array. It costs
   nothing for frames without depth and needs no handshake.
2. **Calibrated cameras from outside FreeMoCap.** `freemocap-stream` builds only
   `uncalibrated_camera` entries. Depth and point clouds need each camera's intrinsics
   (here, after rectification: fx = fy, cx, cy, no distortion) and its pose. A
   `calibrated_camera(id, index, size, intrinsics, extrinsics)` helper producing FreeMoCap's
   own camera shape would let depth ride in a `frame` message and let FreeMoCap's 3D view
   place it.
3. **Two coordinate conventions meet in depth.** Frames declare FreeMoCap's world
   convention (millimetres, right-handed, z up, y forward), while a camera's own frame is
   x to the image's right, y down, z out of the lens. A point cloud crosses both. The
   protocol could name the camera optical frame alongside the world convention, so a
   producer states which one its numbers use rather than describing it in prose, as
   UltraSkelly's `camera.axes` does now.

## What made viewers harder to write

These come from UltraSkelly's dashboard work and match its earlier review
([sdk-external-review.md](sdk-external-review.md)).

- **One newest-wins slot per source.** With the OAK and the ZED both streaming, a single
  decode-in-progress slot let one camera's frames displace the other's; the dashboard keys
  a slot by the camera IDs in each payload, read before decoding. A per-source scheduler,
  or a source key passed with each image, would save every multi-camera viewer that work.
- **Decoding at display size.** `decodeImageBitmaps` checks each bitmap against the header
  size, so a viewer cannot ask the browser for a smaller decode. On the Pi, two 672×376
  eyes shown as small tiles are decoded at full size.
- **Frame numbers are per source.** Overlays pair with their image by frame number, and
  separate cameras count separately, so numbers repeat across sources. Filtering by camera
  ID is enough today; an identity per message would remove the trap.
- **Every viewer decodes depth itself.** Registering `depth_frame` as a kind is easy, but
  inflating the bytes, reading little-endian uint16 and unprojecting with the intrinsics
  are left to each consumer. A client `decodeDepthFrame` returning millimetres, intrinsics
  and pose, usable in a worker, with a matching `freemocap_stream` encoder, would make depth
  the SDK's payload rather than one application's.
- **Decoding starts on the main thread.** The client parses and validates each message
  before a consumer sees it, so a viewer that decodes depth in a worker first copies the
  bytes out (the decoder may reuse its storage) and posts them. An option to receive a
  kind's raw message bytes, or its byte strings as transferable copies, would let the whole
  decode leave the page's thread.
- **Depth arrives apart from its frame.** `depth_frame.frame_number` names the stereo pair it
  came from, but the pair, the preview frames and the depth travel as separate messages, each
  with its own delivery order and newest-wins handling. Depth inside the frame message
  (recommendation 1) would share the frame's identity and its slot.
- **A camera's pose in a body is a local convention.** `camera_to_head` (rotation rows, a
  translation in metres, a named target frame and a `nominal` status) is UltraSkelly's own.
  If camera entries could carry an optional extrinsic to a named rig frame, with a status
  such as `nominal`, `designed` or `measured`, any 3D viewer could place such a camera the
  same way.

## Recommendations

1. Add an optional lossless depth block to the frame message, with a Python writer and a
   worker-safe client reader (`decodeDepthFrame`), before a second application invents
   another depth message.
2. Add `calibrated_camera` to `freemocap-stream`, with an optional extrinsic to a named rig
   frame and its status, and name the camera optical frame in the protocol next to the
   world convention.
3. Offer per-source newest-wins decoding, decode-at-size and raw message bytes for worker
   decoding in `@freemocap/client`.

## Not verified

The browser side of `depth_frame` now runs in UltraSkelly's dashboard
([depth views](https://github.com/freemocap/ultraskelly/blob/a89aead/docs/dashboard.md#depth)):
a worker inflates and colours the millimetres, and vertex shaders unproject them onto the
head. Against the synthetic sample, whose geometry is known, every depth pixel landed
within 0.5 mm of its surface. On the Pi, replaying recorded samples at 5 depth frames a
second, Chromium used about one core. Live depth from the real matcher with the dashboard
on the same Pi is not measured yet. `DecompressionStream` support across browser versions
was not checked against compatibility data. The camera pose in each message is nominal until the robot's camera
bracket gives the real one.
