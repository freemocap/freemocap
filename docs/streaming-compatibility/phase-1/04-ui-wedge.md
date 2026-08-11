# FMC-WS-4 — UI Wedge: Transport Service + Standard-Stream Decoder + Rolling-Window Stores

> **Build order: 3rd** (can run parallel with FMC-WS-2 once FMC-WS-1 golden bytes exist).
> Depends on: FMC-WS-1 (contract — for cross-language golden-byte parity).
> **Status: plan — executable detail below.**
>
> The `ServerContextProvider` (~600 lines) is a God object: connection lifecycle, message routing
> (one giant switch), frame decode/ack loop, 3D data fan-out via hand-rolled subscriber sets,
> framerate/log stores, tracker schemas, and Redux glue. This workstream extracts connection
> lifecycle + message routing into a standalone transport service, adds a standard-stream decoder,
> and introduces **rolling-window stores** that retain the last N frames per channel so trails
> and time-series plots come for free. The remaining God-object decomposition (frame/canvas loop)
> is Phase 3.

## Goal

1. **Transport service** — owns `WebSocketConnection`, connect/reconnect/state, and a **routing
   table** that features register into instead of editing one giant `handleMessage` switch.
2. **Standard-stream decoder (TS)** — parse `stream_schema` (JSON, register channel names +
   convention + hierarchy) then `stream_sample`s (binary blocks, index by position + cross-check
   `block_kind`). Mirror FMC-WS-1's wire layout exactly.
3. **Rolling-window stores** — the decoded sample blocks accumulate into per-channel ring buffers
   (default ~100 frames, configurable). This enables time-series trails and plots. Mirrors
   what the spec doc 05 calls for: "route the 3D samples into time-series stores that retain a
   rolling window per keypoint/channel…fast and memory-bounded."
4. **Rotation data arrives at the viewport** — `ROTATIONS_WORLD` + `ROTATIONS_LOCAL` blocks are
   decoded and fanned out to a new subscriber set (`subscribeToRotations`), ready for the
   `RigidBodyBoneRenderer` to consume.
5. **`ServerContextProvider` becomes a thin consumer** — it no longer owns the socket or the
   routing switch; it consumes the transport service and provides backward-compatible
   subscriber hooks.

## Architecture (target)

```
┌─ TransportService (new, plain TS class) ───────────────────────────────┐
│                                                                         │
│  WebSocketConnection  ← socket ownership, connect/reconnect/state       │
│                                                                         │
│  RoutingTable                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ message_type          → handler                                    │ │
│  │ "stream_schema"       → SchemaRegistry.register(schema)            │ │
│  │ binary (sample msg 10)→ SampleDecoder.decode(buf, schema)          │ │
│  │ binary (legacy keys 3)→ LegacyKeypointsParser.parse(buf)  [temp]   │ │
│  │ "frontend_payload"    → LegacyJsonPayloadHandler  [temp]           │ │
│  │ "framerate_update"    → FramerateStore.update(...)                 │ │
│  │ "app_state"           → Redux dispatch(serverStateReceived(...))   │ │
│  │ ...                                                                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  SchemaRegistry  ← holds the active StreamSchema                        │
│                                                                         │
│  RollingWindowStores  ← per-channel ring buffers, last N frames         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ channel "skeleton_points"  → RollingWindow<Float32Array>(100)      │ │
│  │ channel "rotations_world"  → RollingWindow<Float32Array>(100)      │ │
│  │ channel "rotations_local"  → RollingWindow<Float32Array>(100)      │ │
│  │ channel "center_of_mass"   → RollingWindow<Float32Array>(100)      │ │
│  │ ...                                                                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

ServerContextProvider  (thin — consumes TransportService, exposes subscriber hooks)
        │
        ▼
  useServer() / useKeypointsSource()  ← existing hooks, unchanged contract
```

## Files

### New files

| File | Role |
|---|---|
| `freemocap-ui/src/services/server/transport/TransportService.ts` | Owns the WebSocket, RoutingTable, connect/reconnect lifecycle. Plain TS class — no React. |
| `freemocap-ui/src/services/server/transport/RoutingTable.ts` | Map of message_type → handler + binary first-byte demux. Features register routes via `register(type, handler)`. |
| `freemocap-ui/src/services/server/transport/StandardStreamDecoder.ts` | Decodes `stream_schema` (JSON → `StreamSchema`) + `stream_sample` (binary → `DecodedSample`). Golden-byte parity with FMC-WS-1. |
| `freemocap-ui/src/services/server/transport/SchemaRegistry.ts` | Holds active `StreamSchema`. Resolves sample block indices → channel names. |
| `freemocap-ui/src/services/server/transport/RollingWindowStore.ts` | Generic ring buffer: `push(sample)`, `getLast(n)`, `subscribe(cb)`. Fixed memory — old frames are overwritten. |
| `freemocap-ui/src/services/server/transport/types.ts` | TS mirrors of `StreamSchema`, `ChannelGroup`, `ChannelKind`, `CoordinateConvention`, `RestPose`, `DecodedSample`, `RotationsFrame`. |

### Evolved files

| File | Change |
|---|---|
| `ServerContextProvider.tsx` | **[major shrink]** Socket ownership + `handleMessage` switch move to `TransportService`. Provider becomes a thin consumer exposing subscriber hooks. ~600 → ~200 lines. |
| `server-context.ts` | **[evolve]** `ServerContextValue` adds `subscribeToRotations`, `getLatestRotations`, `getRollingWindow( channelName )`. |
| `KeypointsSourceContext.tsx` | **[evolve]** `KeypointsSource` adds rotation subscriber + rolling-window accessor. |
| `keypoints-protocol.ts` | **[keep]** Legacy constants kept for backward-compat during transition. |
| `keypoints-binary-parser.ts` | **[keep]** Legacy parser kept for backward-compat. |
| `websocket-connection.ts` | **[fold]** Folded into `TransportService`. |

## TypeScript types (mirroring FMC-WS-1)

```typescript
// transport/types.ts

enum ChannelKind {
  POINTS = 0,
  ROTATIONS = 1,         // LEGACY — removed after transition
  OVERLAY_2D = 2,
  ROTATIONS_WORLD = 3,
  ROTATIONS_LOCAL = 4,
}

interface ChannelGroup {
  kind: ChannelKind;
  names: string[];
  columns: string[];
  units: string;
}

interface RestPose {
  positions: Record<string, [number, number, number]>;
  reference_orientations: Record<string, [number, number, number, number]>;
}

interface StreamSchema {
  stream_id: string;
  stream_name: string;
  coordinate_convention: CoordinateConvention;
  channels: ChannelGroup[];
  connections: [string, string][];
  joint_hierarchy: Record<string, string[]>;
  rest_pose: RestPose | null;
  camera_ids: string[];
  max_persons: number;
  message_type: "stream_schema";
}

interface DecodedSample {
  timestamp: number;
  frame_number: number;
  subject_id: number;
  blocks: TypedArrayBlock[];
}

interface TypedArrayBlock {
  kind: ChannelKind;
  data: Float32Array;      // (num_elements * cols) interleaved
  numElements: number;
  cols: number;
  cameraId: string;         // set for OVERLAY_2D blocks
}

interface RotationsFrame {
  boneNames: readonly string[];
  worldQuaternions: Float32Array;   // (numBones * 4)
  localQuaternions: Float32Array;   // (numBones * 4)
}
```

## Rolling-window stores

```typescript
// RollingWindowStore.ts

interface RollingWindowConfig {
  maxFrames: number;       // default 100
  maxAgeMs: number | null; // optional — evict older than this (null = no age limit)
}

class RollingWindowStore<T> {
  constructor(config: RollingWindowConfig) {}

  /** Push one frame's data. Oldest frame is evicted if over maxFrames. */
  push(frame: T): void;

  /** Get the last N frames (most recent first). Default: all in window. */
  getLast(n?: number): T[];

  /** Subscribe to every push. Returns unsubscribe function. */
  subscribe(cb: (frame: T) => void): () => void;

  /** Number of frames currently in the window. */
  get length(): number;

  /** Drop all frames. */
  clear(): void;
}
```

After each `DecodedSample` is decoded, `SchemaRegistry` resolves its blocks and pushes them
into the corresponding `RollingWindowStore` instances. Renderers can then either subscribe
to the latest frame (for live visualization — same as today) or pull the last N frames
(for trails and time-series — new capability).

The stores are keyed by channel index / kind. For example:
- `store["skeleton_points"]` → `RollingWindowStore<KeypointsFrame>`
- `store["rotations_world"]` → `RollingWindowStore<RotationsFrame>`
- `store["center_of_mass"]` → `RollingWindowStore<Point3d>`

Memory is bounded: 100 frames × 55 bones × 4 floats × 4 bytes = ~88 KB per rotation channel,
~66 KB for skeleton points — negligible.

## Sample decode flow

```
Binary message arrives (first byte = 10 = SAMPLE_HEADER)
        │
        ▼
StandardStreamDecoder.decodeSample(buf, schema)
        │
        ├─ Parse SAMPLE_HEADER (timestamp, frame_number, subject_id, num_blocks)
        ├─ For each block (0..num_blocks-1):
        │    ├─ Parse BLOCK_HEADER (block_kind, cols, num_elements, camera_id, ...)
        │    ├─ Validate block_kind matches schema.channels[i].kind
        │    └─ Read BLOCK_DATA → Float32Array(num_elements * cols)
        ├─ Validate SAMPLE_FOOTER
        └─ Return DecodedSample
                │
                ▼
SchemaRegistry.resolveSample(sample, schema)
        │
        ├─ Block 0 (POINTS, skeleton)    → KeypointsFrame → store["skeleton_points"].push()
        │                                 → fire keypointsSubscribers
        ├─ Block 1 (POINTS, derived)     → { centerOfMass, xcom } → store["com"].push()
        │                                 → fire comSubscribers
        ├─ Block 2 (ROTATIONS_WORLD)     → RotationsFrame → store["rotations_world"].push()
        ├─ Block 3 (ROTATIONS_LOCAL)     → RotationsFrame → store["rotations_local"].push()
        │                                 → fire rotationsSubscribers
        ├─ Block 4..4+C-1 (OVERLAY_2D)   → per-camera 2D arrays
        │                                 → fire overlaySubscribers
        └─ All subscribers notified in schema channel order
```

## Transition: dual-protocol coexistence (unchanged)

Legacy bytes 3-5, new bytes 10-12. No collision. `RoutingTable` demuxes on first byte.
Legacy path kept during transition, removed after confirmation.

## Task checklist

1. [ ] **Write `types.ts`** — all TS types mirroring `stream_schema.py`, `stream_sample.py`,
      `coordinate_convention.py`.
2. [ ] **Write `StandardStreamDecoder.ts`** — `decodeSchema(json)` + `decodeSample(buf, schema)`.
      Golden-byte test against FMC-WS-1's test fixture.
3. [ ] **Write `SchemaRegistry.ts`** — holds active `StreamSchema`, resolves sample blocks to
      `KeypointsFrame` + `RotationsFrame` + derived points + overlay blocks.
4. [ ] **Write `RollingWindowStore.ts`** — generic ring buffer as sketched above. Unit test:
      push N+1 frames, only last N retained; subscribe fires on push.
5. [ ] **Write `RoutingTable.ts`** — message_type → handler map; binary first-byte demux.
6. [ ] **Write `TransportService.ts`** — owns `WebSocketConnection` + `RoutingTable` +
      `StandardStreamDecoder` + `SchemaRegistry` + `RollingWindowStore`s. Connect/reconnect.
      Exposes `on(event, handler)` / `off(event, handler)`.
7. [ ] **Shrink `ServerContextProvider.tsx`** — remove socket ownership + `handleMessage` switch.
      Consume `TransportService`. Keep subscriber hooks and add `subscribeToRotations`,
      `getLatestRotations`, `getRollingWindow(channelName)`.
8. [ ] **Add rotation + rolling-window hooks** to `ServerContextValue` + `KeypointsSource`.
9. [ ] **Wire legacy compat** — `RoutingTable` dispatches legacy messages during transition.
10. [ ] **Golden-byte test** — Python golden sample bytes → TS decoded values match.
11. [ ] **Integration test** — connect → schema → samples → `subscribeToRotations` fires →
      `getRollingWindow("rotations_world").length` grows to maxFrames, then stays bounded.

## Tests

- `test_decode_schema_roundtrip` — JSON → `StreamSchema` → channel count, kinds, max_persons.
- `test_decode_sample_golden` — Python golden bytes → TS `DecodedSample` correct.
- `test_rolling_window_eviction` — push 101 frames, only 100 retained, oldest evicted.
- `test_rolling_window_subscriber` — push → subscriber fires with correct frame.
- `test_dual_protocol` — legacy + standard-stream messages coexist, both dispatch.
- `test_overlay_blocks_per_camera` — C cameras → C OVERLAY_2D blocks, camera_ids match schema.

## NOT in scope

- Frame/canvas loop extraction (Phase 3).
- `RigidBodyBoneRenderer` — separate workstream (FMC-RB). Rotation data is available; the
  renderer consumes it.
- One-way-WebSocket decision + stale-UI-after-crash (spec doc 05 — not fixed now).
