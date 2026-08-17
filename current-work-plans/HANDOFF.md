# Handoff — backend self-describing CBOR frame COMPLETE; frontend dispatcher is next

> **For a fresh agent (or post-compaction).** This is the authoritative live snapshot: the state, the
> data model, the WHY, and the next work. Docs and code both drift; neither is authoritative — err on
> "best system" and read whichever artifact was written most recently. The WHY sections are the most
> load-bearing thing in this repo — internalize them before touching code.

## One-sentence state

The **backend wire is now a self-describing CBOR frame document** — no schema, no samples, no
replace-kinds. Five kinds (`frame`, `log`, `framerate`, `app_state`, `progress`); the `frame` carries
convention + calibrated cameras + model definitions + per-frame instances + tracker observations +
image, all in ONE self-contained message. **The frontend still expects the old schema/sample wire and
is BROKEN until step 3 (the dispatcher).**

## The data model (what the wire actually is now)

All wire types are frozen-slots dataclasses. Every top-level message COMPOSES a `MessageEnvelope`
(version/timestamp/sequence) and declares a `ClassVar kind`. A `@runtime_checkable Message` Protocol is
the structural contract (composition over inheritance — no base class). `to_cbor_message()` returns
plain CBOR-encodable types (dict/list/scalar); only `encode_message` imports cbor2.

```
FrameMessage (freemocap/core/streaming/message_model.py):
  envelope: MessageEnvelope          # composed (version/timestamp/sequence), flattened on encode
  kind: ClassVar = "frame"
  frame_number: int
  model_sequence: int                # bumps only when the model changes → client cache invalidation
  convention: CoordinateConvention   # units/handedness/up_axis/forward_axis/rotation_frame/rotation_form
  cameras: tuple[CalibratedCamera]   # id/index/image_size/intrinsics{fx..p2}/extrinsics{quat+translation}/world_position/world_orientation
  models: tuple[ModelDefinition]     # model_id + segments[RestSegment] + landmarks[RestLandmark]
  instances: tuple[ModelInstance]    # instance_id + model_id + channels[ChannelBlock]  (reconstruction)
  trackers: tuple[TrackerObservation]# tracker_id + detector_type + model_id + channels[ChannelBlock]  (keypoints)
  image: bytes | None                # the opaque multi-camera JPEG blob
```

```
RestSegment (skellyforge/skellymodels/standard_human/rest_pose.py — the "third thing"):
  name, parent, longitudinal_axis, rest_orientation (wxyz), length_mm, rigid_with_parent
  longitudinal_axis = a signed basis axis ("x"/"y"/"z"/"-x"/… ) OR a normalized 3-vector
  (it is the vector origin→child, or origin→tip for a leaf).

ChannelBlock: kind + columns + data (packed float32 LE bytes) + camera_id? + names?
  names is inline ONLY on non-model channels (KEYPOINTS_3D / OVERLAY_2D / DERIVED_POINTS).
  Segment/landmark channels are INDEX-KEYED against the model's ordered symbol tables (names dropped).
```

Channel routing by kind: KEYPOINTS_3D / OVERLAY_2D → trackers; everything else → instances.

## The WHY (load-bearing principles — internalize before any edit)

1. **Self-describing, not schema-then-samples.** The old wire made decode correctness depend on a
   separately-held descriptor; a stale descriptor decodes WRONG with no error (silent desync across
   independent browser/server restarts). Every frame is now complete on its own.
2. **decode-complete vs render-complete.** CBOR + inline names = decode-complete (bytes→typed values,
   zero state). Rendering bones still joins rows against the held model slice — render-complete, which
   we deliberately do NOT claim. Honesty about this boundary is load-bearing.
3. **Plain byte strings for packed float32, never typed-array tags.** Avoids the float16 downcast
   (silent precision loss) + the cbor2-vs-cbor-x tag-identity risk. Scalar floats stay float64.
4. **Composition over inheritance.** MessageEnvelope is composed (not a base class); the Message
   Protocol + runtime isinstance is the guarantee. No ABC.
5. **Co-location by semantics.** Resolved-model primitives (LongitudinalAxis/RestSegment/RestLandmark)
   live in SKELYFORGE (the "third thing" completing the ontology, near SegmentDefinition/ReferenceGeometry).
   Wire assembly (ModelDefinition/FrameMessage/CalibratedCamera/envelope/kinds) lives in FREEMOCAP, which
   imports skellyforge (allowed direction; SkellyForge never imports FreeMoCap).
6. **Full model every frame.** The whole point is statelessness — do NOT re-litigate "minimal then grow"
   (that reintroduces held-state desync). The model is ~14 KB; the JPEGs dwarf it (~4-12% tax, irrelevant
   on localhost).
7. **Index-keyed channels.** Names appear once per frame (in the model/tracker); channels reference by
   row order. This also kills the old O(n²) name lookups in the renderer hot path.
8. **Type aliases, not raw str/int.** CameraIdString / CameraIndexInt / CameraGroupIdString from
   skellycam.core.types.type_overloads. Never `Any` for a camera id.
9. **Import hygiene (mediapipe landmine).** The producer chain pulled mediapipe via pubsub_topics →
   realtime config → camera config → skellytracker mediapipe. Fixed by duck-typing the aggregator output
   as `Any` in producer_contexts.py + channel_helpers.py (NOT TYPE_CHECKING — beartype can't resolve
   string annotations whose names aren't in module globals). Heavy imports stay OUT of module top level.
10. **`to_cbor_message()` is the conversion method name** (not to_cbor_map / to_message).

## Naming rules (hard-won — a prior agent was corrected repeatedly; enforce ruthlessly)

- No single-word file names; no single-word public class/function names (index/store/hooks exempt).
- No import aliasing for internal imports; NEVER import old-into-new; positive definitions.
- Vocabulary: message / kind / channel / ChannelBlock / FrameMessage / RestSegment / RestLandmark /
  ModelInstance / TrackerObservation / CalibratedCamera / CoordinateConvention / longitudinal_axis.
- NEVER: schema / sample / standard_stream / ChannelGroup / SampleBlock / StreamSchema / StreamSample /
  subject (→ instance) / canonical (→ standard human) / "long axis" / "defining axis".
  (Legit "schema" stays: tracker schema = TrackedObjectDefinition for playback; OpenAPI schema.)
- skellyforge authoring: exact_axis (signed "x"/"y"/"z"/"-x"/… ) + rest_direction (a world vector, NOT
  euler). rest_rotation (euler) and _TWIST_OVERRIDES are GONE.

## The next work — frontend step 3 (the dispatcher)

The frontend demux is SPLIT: TransportService owns stream_schema JSON + binary sample (RoutingTable +
StandardStreamDecoder + SchemaRegistry); ServerContextProvider owns a SEPARATE transport.on('message')
JSON if/else (websocket-message-types.ts isX guards). Step 3 unifies into ONE kind-keyed dispatcher.

Files: TransportService.ts (decode CBOR via cbor-codec.decodeMessage + route by kind); RoutingTable.ts
(→ kind dispatcher); ServerContextProvider.tsx (delete the JSON if/else → thin ~200-line root); NEW RTK
slices model/convention/camera_layout; RigidBodyBoneRenderer.tsx + KeypointsSourceContext.tsx re-point
from getStreamSchema() to the model slice; DELETE StandardStreamDecoder.ts / SchemaRegistry.ts /
wire-types.ts / websocket-message-types.ts + old goldens + decoder test.

Client homes: frame→frame subscribers (fast); convention/model/camera_layout/app_state/progress→RTK slices
(replace); log→LogStore (append); framerate→FramerateStore (fast).

Risks: (a) model-before-frames — route model→slice; (b) app_state cross-slice (cameras+realtime) — dispatch
the SAME action; (c) tracker_schemas handshake is dead but TrackedObjectDefinition + ConnectionRenderer +
getActiveSchema are LIVE for playback — delete only the handshake; (d) inbound frameAcknowledgment
(displayImageSizes) stays; (e) image is the opaque multi-camera JPEG blob (binary-frame-parser.ts).

Note: the frontend message-contract.ts (Zod union) + cbor-codec.ts (cbor-x decode) are step-1 artifacts
that still mirror the OLD flat frame — they must be updated to the NESTED frame shape above.

## Cross-repo reality

- freemocap installs skellyforge/skellytracker/skellycam/skellylogs FROM GIT (uv sources). A local skelly
  edit is invisible to freemocap until commit+push+uv-sync. The USER owns ALL git — never commit/push.
- skellyforge: rest_pose.py (`rest_position` optional) may be UNCOMMITTED — commit+push+uv-sync before the
  freemocap tests see it.

## Env / gotchas (sandbox)

- mediapipe/sounddevice import crashes the sandbox (native access violation). The composer/producer chain
  is importable now (duck-typed Any fix); the full-loop tests need the USER.
- No pytest in the freemocap venv. Use skellytracker\\.venv\\Scripts\\pytest.exe + PYTHONPATH, or run test
  functions directly.
- Backend subset (run by USER): uv run --group dev pytest freemocap/tests/rigid_body/
  freemocap/tests/test_center_of_mass.py freemocap/tests/test_message_model.py freemocap/tests/test_send_serializer.py
  freemocap/tests/test_frame_relay.py freemocap/tests/test_full_loop.py freemocap/tests/kinematics/ -q
- Golden regen: python freemocap/tests/streaming_fixtures/regenerate_message_golden.py
- Line endings: freemocap = LF; skellyforge/skellycam = CRLF.
