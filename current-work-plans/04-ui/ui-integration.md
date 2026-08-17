# UI Integration (the message dispatcher + the decomposition)
> **Superseded (2026-08-16):** this doc describes the pre-cutover design. The wire was redesigned — the
> frame is now a fully self-describing document (nested convention/cameras/models/instances/trackers/image;
> 5 kinds). The authoritative current shape + WHY live in **HANDOFF.md** — read it first.
>


**Describes:** freemocap-ui/src — TransportService (the dispatcher), ServerContextProvider (thin), and
the client homes (RTK slices + fast stores). This completes the ServerContextProvider decomposition from
the archived specs 05 and 04-ui-wedge, now with a single self-describing message model instead of the
schema/sample model.

## The dispatcher lives in TransportService

TransportService owns the WebSocket and the dispatch: decode a CBOR message, validate it against the Zod
discriminated union (01-data-model/message-contract.md), then route by kind to its home.

| kind | home | pattern |
|---|---|---|
| frame | frame subscribers -> ServerContextProvider fan-out -> WorkerDataStore | fast (emit) |
| convention | new RTK slice | replace |
| model | new RTK slice | replace |
| camera_layout | new RTK slice | replace |
| calibration | calibration slice | replace |
| log | LogStore | append |
| framerate | FramerateStore | fast |
| app_state | connection slice | replace |
| progress | pipelines/mocap/calibration slices | replace |

An unknown kind or version is logged once and skipped.

## ServerContextProvider becomes thin

Today ServerContextProvider is ~599 lines and still owns the connection lifecycle, the frame decode/ack
loop, the hand-rolled subscriber sets, and the JSON if/else chain (log, framerate, progress, app_state,
tracker_schemas). The wedge (spec 05) extracted routing + connection into TransportService but only wired the old
standard-stream (schema/sample) path; the rest of the if/else chain never migrated. This plan finishes that migration:

- The JSON if/else chain + hand-rolled isX guards are deleted; kinds route through the dispatcher.
- The frame decode/ack loop and the FrameProcessor/CanvasManager wiring move to a rendering-orchestration
  module (spec 05 step 2).
- The subscriber sets stay as the fan-out to the viewport worker (unchanged consumer contract).
- ServerContextProvider ends as a thin composition root (~200 lines) that wires kinds to homes.

## Preservation inventory (nothing live is lost)

| today (server -> client) | becomes | notes |
|---|---|---|
| schema: convention, rest-pose, axes, hierarchy, camera sizes | convention + model + camera_layout kinds | replaced schema |
| sample: pose + overlays + images + lengths | frame kind | same payload, self-describing |
| logs | log kind | same LogStore |
| framerate_update | framerate kind | same FramerateStore |
| app_state | app_state kind | same connection slice |
| posthoc_progress | progress kind | same pipelines/mocap/calibration slices |
| tracker_schemas | removed (handshake only) | the websocket handshake is dead (backend source deleted). The `TrackedObjectDefinition` TYPE + `ConnectionRenderer` + `getActiveSchema` stay — they are the playback stick-figure's connection source, not this wire |

Inbound (client -> server): the frameAcknowledgment with displayImageSizes stays. HTTP/thunks (cameras,
recording, videos, realtime apply, mocap, blender) are untouched.

## Migration

Hard cutover, no dual format. Order: (1) define the Zod union + CBOR decode; (2) backend emits the new
messages; (3) dispatcher routes kinds to homes; (4) delete StreamSchema/ChannelGroup/SchemaRegistry, the
isX guards, and the schema/sample decode path; (5) shrink ServerContextProvider. Each step is verifiable
against the preservation table above.