# UI Integration (the message dispatcher + the decomposition)

**Describes:** `freemocap-ui/src` — TransportService (the dispatcher), ServerContextProvider (thin), and
the client homes (RTK slices + fast stores).

## The dispatcher lives in TransportService

TransportService owns the WebSocket and the dispatch: decode a CBOR message, validate it against the Zod
contract ([01-data-model/message-contract.md](../01-data-model/message-contract.md)), then route by kind
to its home.

| kind | home | pattern |
|---|---|---|
| frame | frame subscribers → ServerContextProvider fan-out → canvas + viewport workers | fast (emit) |
| log | LogStore | append |
| framerate | FramerateStore | fast |
| app_state | connection slice (serverStateReceived) | replace |
| progress | pipelines/mocap/calibration slices | replace |

An unknown kind or version is logged once and skipped.

## ServerContextProvider becomes thin

TransportService owns the frame decode + kind dispatch; ServerContextProvider wires the subscriber sets
and the canvas/worker rendering. The subscriber sets remain as the fan-out to the viewport worker. The frame's
overlay + image are handled by the canvas workers; the 3D rigid-body renderer reads the frame's
self-describing model + rotations directly.

## Preservation inventory (nothing live is lost)

| was (schema/sample wire) | is now (self-describing) |
|---|---|
| schema: convention, rest-pose, axes, hierarchy, camera sizes | the frame's convention + cameras + models (every frame) |
| sample: pose + overlays + images + lengths | the frame's instances + trackers + image (every frame) |
| logs | log kind |
| framerate_update | framerate kind |
| app_state | app_state kind |
| posthoc_progress | progress kind |
| tracker_schemas handshake | removed — `TrackedObjectDefinition` stays for the playback stick-figure, not this wire |

Inbound (client → server): the frameAcknowledgment with displayImageSizes stays. HTTP/thunks (cameras,
recording, videos, realtime apply, mocap, blender) are untouched.
