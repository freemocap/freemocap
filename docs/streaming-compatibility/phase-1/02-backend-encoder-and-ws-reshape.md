# FMC-WS-2 — Backend Encoder + WebSocket Send-Path Reshape

> **Build order: 2nd** (after FMC-WS-3). Depends on: FMC-WS-1 (contract), FMC-WS-3 (schema).
> **Status: plan — executable detail below.**
>
> Channel content is defined in [09 § channels](../09-standard-stream-protocol.md#channels) — the encoder
> implements against it and this plan never redefines it. Terms — *keypoint* / *landmark* / *segment* — per
> [13](../13-tracker-to-canonical-mapping.md#two-kinds-of-trajectory).
>
> **Landmark reprojection is new scope for this workstream** ([09 § 2D
> overlays](../09-standard-stream-protocol.md#2d-overlays-detections-and-reprojections)): the encoder needs
> the fitted landmarks projected into each camera, read from the existing calibration.
>
> This is the most invasive backend change in Phase 1. It replaces the current dual-path send
> (`FrontendPayload` JSON + legacy binary keypoints) with the standard stream (schema once +
> timestamped samples) and breaks up the monolithic `WebsocketServer` send path into focused,
> testable components. Image data stays a separate stream throughout.

## Goal

1. **`StreamSample.from_aggregator_output()`** + **`.to_bytes()`** — classmethods/instance methods on
   the FMC-WS-1 types, replacing freestanding builder/encoder functions with large parameter lists.
   Same classmethod pattern as FMC-WS-3's `StreamSchema.from_standard_human()`.
2. The **WebSocket send path** is decomposed: send-serializer, frame relay, backpressure controller
   with configurable in-flight window. `WebsocketServer` becomes a thin supervisor.
3. The **legacy path is retired**: `build_keypoints_payload`, `FrontendPayload` numeric fields
   (CoM/xcom), `TrackerSchemasMessage` — all replaced by the standard stream.
4. **Image data stays separate** — still relayed as JPEG bytearrays, linked by frame number.

## Data flow (target)

```
AggregationNodeOutputMessage  (pubsub — has rotations, CoM, xcom, skeleton, keypoints, overlays)
        │
        ▼
  StreamSample.from_aggregator_output(msg, schema, timestamp, subject_id)  →  StreamSample
        │
        ▼
  sample.to_bytes()  →  bytes on the wire
        │
        ▼
  FrameRelay  (reads latest frame, builds sample, sends via SendSerializer)
        │
        ▼
  SendSerializer  (owns _send_lock, serializes all WS writes)
        │                                                  │
        ▼                                                  ▼
  WebSocket send_text(schema_json)              WebSocket send_bytes(sample_binary)
  (once on connect/change)                      (per frame)
        │                                                  │
        └────────────┬─────────────────────────────────────┘
                     │
                     ▼
              Frontend decodes schema → indexes sample blocks by position → renders
```

## Files

### Evolved files (FMC-WS-1 types)

| File | Change |
|---|---|
| `freemocap/core/streaming/standard_stream/stream_sample.py` | **[evolve]** Add `StreamSample.from_aggregator_output()` classmethod. Add `StreamSample.to_bytes()` instance method and `StreamSample.from_bytes(buf)` classmethod — thin wrappers around the existing `encode_sample()`/`decode_sample()` functions. |
| `freemocap/core/streaming/standard_stream/stream_schema.py` | **[evolve]** FMC-WS-3 already adds `from_standard_human()`. Schema is serialized with the existing `encode_schema()`. |

### New files

| File | Role |
|---|---|
| `freemocap/api/websocket/backpressure_controller.py` | Pure policy object: configurable in-flight window, ack-lag thresholds, reset logic. No I/O — unit-testable. |
| `freemocap/api/websocket/send_serializer.py` | Owns the `_send_lock` + one-writer invariant. |
| `freemocap/api/websocket/frame_relay.py` | Waits on frame source, calls `StreamSample.from_aggregator_output()`, serializes via `.to_bytes()`, hands to SendSerializer. Delegates backpressure decisions. |

### Evolved files (pipeline)

| File | Change |
|---|---|
| `freemocap/api/websocket/websocket_server.py` | **[major refactor]** Thin supervisor composing SendSerializer + FrameRelay + BackpressureController. Old `_frontend_image_relay` replaced by FrameRelay + separate image relay. ~430 → ~100 lines. |
| `freemocap/core/viz/frontend_payload.py` | **[shrink]** `FrontendPayload` stripped to image-only metadata. `from_aggregation_output()` deleted. |
| `freemocap/core/viz/frontend_keypoints_serializer.py` | **[retire]** Replaced by `StreamSample.from_aggregator_output()` + `.to_bytes()`. |
| `freemocap/api/websocket/tracker_schema_message.py` | **[retire]** Replaced by `encode_schema()` on connect. |
| `freemocap/app/freemocap_application.py` | **[evolve]** `get_latest_frontend_payloads` feeds the aggregator output to `StreamSample.from_aggregator_output()`. |

## Component detail

### `StreamSample` classmethods

```python
# stream_sample.py — additions (thin, delegates to existing encode/decode fns)

@dataclass(slots=True)
class StreamSample:
    timestamp: float
    frame_number: int
    subject_id: int
    blocks: list[SampleBlock] = field(default_factory=list)

    @classmethod
    def from_aggregator_output(
        cls,
        *,
        schema: StreamSchema,
        msg: "AggregationNodeOutputMessage",  # freemocap import
        timestamp: float,
        subject_id: int = 0,
    ) -> "StreamSample":
        """Build a standard-stream sample from one aggregator frame.

        Reads keypoint trajectories, segment origins, rotation quaternions,
        derived points, and both 2D overlay layers from the message. Densifies
        each to the schema's declared name order. Missing points → NaN row.

        Block order and content: 09 section "channels" (the authority).

        This is the single place that maps the aggregator's output dicts
        into the ordered sample blocks. No intermediate FrontendPayload.
        """
        blocks: list[SampleBlock] = []

        # Block 0: KEYPOINTS_3D — triangulated detections, tracker-named
        blocks.append(_build_points_block(
            kind=ChannelKind.KEYPOINTS_3D,
            names=schema.channels[0].names,
            positions=msg.keypoints_arrays,
            errors=msg.raw_errors_px,
        ))

        # Block 1: SEGMENT_ORIGINS — transform origin (proximal joint) per segment
        blocks.append(_build_origins_block(
            names=schema.channels[1].names,
            positions=msg.skeleton,
        ))

        # Block 2: ROTATIONS_LOCAL — parent-relative; the VMC contract
        blocks.append(_build_rotation_block(
            kind=ChannelKind.ROTATIONS_LOCAL,
            names=schema.channels[2].names,
            quaternions=msg.segment_rotations_local,
        ))

        # Block 3: ROTATIONS_WORLD
        blocks.append(_build_rotation_block(
            kind=ChannelKind.ROTATIONS_WORLD,
            names=schema.channels[3].names,
            quaternions=msg.segment_rotations_world,
        ))

        # Block 4: DERIVED_POINTS (CoM, xcom)
        blocks.append(_build_derived_points_block(
            schema=schema,
            com=msg.center_of_mass_result,
            xcom=msg.xcom,
        ))

        # Blocks 5..5+2C-1: OVERLAY_2D — one per (camera, layer)
        for camera_id in schema.camera_ids:
            blocks.append(_build_overlay_block(
                schema=schema,
                camera_id=camera_id,
                layer=OverlayLayer.DETECTIONS,
                overlays=msg.keypoint_overlay_data,
            ))
            blocks.append(_build_overlay_block(
                schema=schema,
                camera_id=camera_id,
                layer=OverlayLayer.REPROJECTIONS,
                overlays=msg.segment_reprojection_data,
            ))

        return cls(
            timestamp=timestamp,
            frame_number=msg.frame_number,
            subject_id=subject_id,
            blocks=blocks,
        )

    def to_bytes(self) -> bytes:
        """Serialize to the binary wire format."""
        return encode_sample(self)

    @classmethod
    def from_bytes(cls, buf: bytes) -> "StreamSample":
        """Reconstruct from the binary wire format."""
        return decode_sample(buf)
```

The existing `encode_sample()` and `decode_sample()` functions stay as the implementation.
`to_bytes()` and `from_bytes()` are thin wrappers — no duplication.

### `BackpressureController`

```python
# freemocap/api/websocket/backpressure_controller.py

from enum import Enum, auto

class BackpressureAction(Enum):
    SEND = auto()   # OK to send next frame
    WAIT = auto()   # in-flight window full — wait for an ack
    RESET = auto()  # frontend hopelessly behind — reset ack counter, proceed


@dataclass
class BackpressureController:
    """Pure policy — no I/O, no asyncio. Unit-testable.

    Allows up to ``window_size`` frames in flight before waiting for a
    frontend ack. This pipelines sends (the backend can encode frame N+1
    while frame N is in the socket buffer) without accumulating an
    unbounded backlog if the frontend truly lags.

    If the frontend falls behind by ``reset_threshold`` frames, the ack
    counter is reset and the backend proceeds — the stale frames are dropped.
    """
    window_size: int = 3        # max unacknowledged frames allowed in flight
    reset_threshold: int = 300  # frames behind → reset rather than stall

    _last_sent: int = -1
    _last_acked: int = -1

    @property
    def unacked_count(self) -> int:
        if self._last_sent < 0:
            return 0
        return max(0, self._last_sent - self._last_acked)

    def ack(self, frame_number: int) -> None:
        self._last_acked = max(self._last_acked, frame_number)

    def sent(self, frame_number: int) -> None:
        self._last_sent = frame_number

    def should_send(self) -> BackpressureAction:
        lag = self.unacked_count
        if lag >= self.reset_threshold:
            return BackpressureAction.RESET
        if lag >= self.window_size:
            return BackpressureAction.WAIT
        return BackpressureAction.SEND
```

`window_size=3` means the backend sends up to 3 frames ahead of the last ack before
pausing. This is the key change from the current system which effectively has `window_size=1`
(waits for every ack before sending the next frame).

## Transition strategy — **under revision (defect D36)**

> This section currently reads: *"Feature flag `FREEMOCAP_STANDARD_STREAM=1`. Dual-protocol coexistence
> during transition. No flag-day."*
>
> That contradicts [00](../00-overview.md)'s **"Zero backwards-compatibility cruft — there is one version of
> the system: the current one"** and locked decision 8 (*"Replace, don't parallel"*). Nothing has shipped
> this wire format, so there is no external consumer to stay compatible with; the only thing dual-protocol
> buys is the ability to keep the legacy path alive, which is the cruft the rule exists to prevent.
>
> **Proposed: delete the flag and the legacy path in one change.** The distinct first-byte tags (legacy
> 3/4/5, standard stream 10/11/12) already prevent collision, so the swap is safe without a flag; the UI
> wedge (FMC-WS-4) lands the decoder in the same cycle. Tracked as **D36** — see
> [FMC-SR §10b](07-spec-reconciliation.md#10b-structure-hygiene-and-contradictions).

## Task checklist

1. [ ] **Add `from_aggregator_output()` classmethod** to `StreamSample` in `stream_sample.py`.
2. [ ] **Add `to_bytes()` / `from_bytes()` methods** to `StreamSample` — thin wrappers.
3. [ ] **Write `SendSerializer`** — extract the `_send_lock` + `send_text`/`send_bytes`.
4. [ ] **Write `BackpressureController`** — with configurable `window_size`. Unit tests:
      SEND when under window; WAIT when window full; RESET when >= reset_threshold.
5. [ ] **Write `FrameRelay`** — compose serializer + backpressure. Calls
      `StreamSample.from_aggregator_output()` → `.to_bytes()` → serializer.
6. [ ] **Segment reprojection** — project the fitted segment model into each camera using the existing
      calibration, and carry the result on the frame so the encoder can emit the `REPROJECTIONS` overlay
      layer ([09](../09-standard-stream-protocol.md#2d-overlays-detections-and-reprojections)). New scope
      from FMC-SR §3.
7. [ ] **Emit both overlay layers** — `2C` blocks per sample, keyed by `(camera_id, overlay_layer)`.
8. [ ] **Update `FrontendPayload`** — strip to image-only; delete `from_aggregation_output()`.
7. [ ] **Refactor `WebsocketServer`** — thin supervisor composing the new components.
8. [ ] **Wire `StreamSchema.from_standard_human()`** — called at startup (FMC-WS-3), result
      fed to the encoder / FrameRelay.
9. [ ] **Retire `build_keypoints_payload`** — replaced by `StreamSample.from_aggregator_output()`.
10. [ ] **Retire `TrackerSchemasMessage`** — replaced by `encode_schema(schema)` on connect.
11. [ ] **Feature-flag the new path** — `FREEMOCAP_STANDARD_STREAM=1`.
12. [ ] **Integration test** — connect → receive schema → receive sample → sample has correct
      block count (5 + C where C = cameras), rotation data non-NaN, overlay blocks keyed by
      camera_id.

## Tests

- `test_backpressure_controller` — SEND under window, WAIT at window, RESET at threshold.
- `test_sample_from_aggregator_output` — synthetic `AggregationNodeOutputMessage` → `StreamSample`
  with correct block kinds, element counts, wxyz values from the solver.
- `test_sample_to_bytes_roundtrip` — `.to_bytes()` → `.from_bytes()` reconstructs identical sample.
- `test_sample_missing_point` — a bone not in the frame → NaN row, visibility 0.
- `test_overlay_per_camera` — N cameras → N OVERLAY_2D blocks, each with correct camera_id.
- `test_image_path_unchanged` — JPEG bytearrays still relayed alongside samples.

## NOT in scope

- UI decode (FMC-WS-4).
- LSL transport route (Phase 2).
- Full God-object decomposition beyond the send path.
- Legacy protocol deletion (kept behind feature flag during transition).
