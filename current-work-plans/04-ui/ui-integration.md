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

## Two frame channels, and one of them is plural

`frame-resolution.ts` resolves a decoded frame into exactly two things:

- **`keypoints`** — every tracker's `KEYPOINTS_3D`, merged. A session runs several detectors and their
  name spaces are disjoint, so concatenating is lossless; taking the first silently dropped the rest.
- **`models: ResolvedModelFrame[]`** — one entry per tracked thing, each carrying its own model
  definition beside its own origins, landmarks, rotations, fitted lengths and derived points.

Origins / rotations / lengths / derived travel as ONE channel because they describe ONE model. Split
into four singular channels (as they were), a consumer could pair a person's rotations with a board's
origins, and every index-keyed row got labelled from `models[0]`'s symbol table regardless of which
instance it came from.

TransportService owns the frame decode + kind dispatch; ServerContextProvider wires the subscriber sets
and the canvas/worker rendering. The frame's overlay + image are handled by the canvas workers.

Overlay observations are **accumulated, not assigned**: several detectors overlay the same camera in one
frame, so `points` and `landmarks` union rather than overwrite. A reprojection overlay carries the
`modelId` it came from and takes its `connections` from **that** model — reading `models[0]` drew a
board's reprojection wearing the human's connection list.

## Renderers are model-driven

The viewport renders from the frame document, and every renderer **iterates models** rather than
reading "the" skeleton:

| renderer | draws | plural strategy |
|---|---|---|
| `ModelConnectionRenderer` | `ModelDefinition.connections` (segment origin→origin) **and** every `landmark_connections` group, each in its resolved colour | one edge plan across all models, replanned only when the model SET changes |
| `RigidBodyBoneRenderer` | oriented cylinders from origins + world rotations + fitted lengths | each model gets a contiguous block of instanced-mesh slots |
| `SegmentAxesRenderer` | per-segment orientation triads | same block-per-model scheme; arm lengths scale with each model's own fitted scale |
| `KeypointsRenderer` | raw merged tracker keypoints, and every model's fitted `LANDMARKS_3D` | landmark colours come from the models' `landmark_groups` |
| `CenterOfMassRenderer` | the balance picture (CoM, ground projection, XCoM) | draws ONE subject — the model reporting an `xcom`, since XCoM is an opt-in derived quantity and a model reporting one is a model that asked for this display |

A model's own row index is what indexes its channel data; the mesh slot is that row plus the model's
block base. Conflating the two is how a second model would overwrite the first's bones.

Adding a channel kind or model field is a renderer concern, never a recompute-the-model concern.

**One connection renderer, not two.** Edges come from the model and nowhere else — never re-derived
from client config, tracker schemas, or by parsing point names. The schema-driven renderer that used to
rebuild aruco quads by splitting `ArucoMarkerCorner-{id}-{j}` is deleted, along with the
`startsWith('arucomarkercorner')` colour check. A frame with a person and a charuco board draws both
from the same code.

**Playback feeds the same path.** A recording carries tracked points and name-pair edges — no segments,
no rotations, no fitted scale — which is an ordinary under-specified model. `playback-model-frame.ts`
expresses it as one: landmarks are the tracked points, edges become landmark-connection groups by side.
That is what let the second renderer, and the whole `schemaState` channel behind it, be deleted rather
than kept alongside.

## The viewport runs in a Web Worker

`ThreeJsCanvas` transfers the canvas to an offscreen worker, and the renderers read `WorkerDataStore`
rather than the server context. **A channel not explicitly forwarded to the worker does not exist
there** — it fails silently and looks like a broken renderer, which is how segment lengths went
missing once already. Every new channel needs its hop through `ThreeJsCanvas` → `WorkerDataStore`.

Collapsing origins/rotations/lengths/derived into the single `modelFrames` message shrinks that hazard:
there is now one forwarding hop for everything a model looks like, so a new per-model field rides across
for free instead of needing its own plumbing.

## Preservation inventory (nothing live is lost)

| was (schema/sample wire) | is now (self-describing) |
|---|---|
| schema: convention, rest-pose, axes, hierarchy, camera sizes | the frame's convention + cameras + models (every frame) |
| sample: pose + overlays + images + lengths | the frame's instances + trackers + image (every frame) |
| logs | log kind |
| framerate_update | framerate kind |
| app_state | app_state kind |
| posthoc_progress | progress kind |
| tracker_schemas handshake | removed — `TrackedObjectDefinition` survives only as playback's input, converted to a `ModelDefinition` before it reaches a renderer |

Inbound (client → server): the frameAcknowledgment with displayImageSizes stays. HTTP/thunks (cameras,
recording, videos, realtime apply, mocap, blender) are untouched.
