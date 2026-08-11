# Implementation Plan & Progress

> **Living document.** This is the authoritative source for *scope* (what we're building and when)
> and *progress* (what's done). The spec docs (`00`–`08`) describe the target system; this file
> tracks the work to get there. Update the [Progress log](#progress-log) as work lands; move items
> between scope buckets deliberately, never silently.

## How to use this document

- The [Scope table](#scope-table-authoritative) is the single source of truth for
  `[IN]` / `[LATER]` / `[FUTURE]` tags used throughout the spec docs.
- Each phase has a checklist. Check items only when they're done and verified per
  [08 — Testing Strategy](08-testing-strategy.md).
- Unknowns are `TBD` with an explicit **trigger** — the event that unblocks them, listed in
  [Dependencies & blockers](#dependencies--blockers).

## Scope table (authoritative)

### `[IN]` — near-term build
- **The LSL-shaped standard stream**: a schema (channels, joint hierarchy, T-pose, convention, units)
  sent once + timestamped samples per frame, mirroring LSL's data model, over the existing WebSocket.
  Backend standard-stream encoder + frontend consumption.
- Canonical-frame extensions: **segment-rotation channels** (via the folded-in `bs/` engine), **subject
  dimension**, **convention/rest-pose in the schema**, **per-point confidence / reprojection error**.
- **Kinematics engine fold-in**: copy/adapt `bs/kinematics_core` into **SkellyForge**; **align** (don't
  delete) the existing `core/kinematics` ([11](11-kinematics-fold-in.md)).
- **Tracker→canonical mapping migration**: finish removing the "virtual marker" concept; add the
  `frame_offset` mapping form for off-surface joint centers (clavicle SC/GH) ([13](13-tracker-to-canonical-mapping.md)).
- **On-disk serialization**: migrate the **parquet** schema to tidy-long ([10](10-serialization-and-tidy-format.md)).
- Streaming hub: frame tap, latest-frame mailbox, derived views, `StreamingManager`, supervision.
- `/streaming/*` HTTP control plane (list / start / streams / stop); scoped fail-loud; **start idle**;
  **ephemeral server-side** config.
- **LSL transport route** (near-free pass-through of the standard stream; `pylsl` is a **core** dep).
- **VMC protocol adapter** (derived from the standard stream).
- Adapter registry (extracted after VMC).
- **UI:** streaming controls in the **Realtime UI** (dropdown of toggles + per-option modal); the
  `ServerContextProvider` **wedge** (message-routing + connection-lifecycle extraction) → full
  decomposition; **3D data → rolling-window time-series stores** (default ~100 frames, settable).
- **`websocket_server.py` breakup** (fused with the standard-stream reshape).
- **Audit `app_state` / inbound "settings"** end-to-end; flag dead paths for removal.

### `[LATER]`
- VRChat OSC adapter; Rokoko JSON adapter.
- **Align** the disabled kinematics code to the new engine/models; keep it out of hot loops until validated
  ([06](06-backend-refactor-and-cleanup.md), [11](11-kinematics-fold-in.md)).
- Scapula (scapulothoracic detail) via the `frame_offset` mechanism ([12](12-standard-human-model.md)).
- Face blendshapes driven from tracked face landmarks (null until wired).
- Dedicated high-frequency `streaming_status` WS message (if `app_state` cadence proves insufficient).
- One-way-WS decision + authoritative-reconnect fix for the stale-UI-after-crash issue.
- UI-side persistence of stream configs.

### `[FUTURE]` / out
- Xsens MVN, Qualisys RT, native Unreal Live Link route (Unreal reachable via VMC today).
- **Not doing:** NatNet, Vicon.
- Retirement of any **confirmed-dead** `app_state` / "settings" fields found during the wedge. (The disabled
  kinematics code is **aligned, not retired** — see `[LATER]`.)

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| *(Resolved — see progress log: kinematics engine → `bs/` copy-in; serialization → parquet tidy-long; standard-human → VRM rig; rest pose → canonical T-pose; incoming-code dependency gone.)* | — | — |
| Forward-axis confirmation of FMC canonical convention | Coordinate converter | Confirm against ground-plane calibration basis |
| Multi-subject keying detail | Subject addressing on the frame | Multi-person tracking design |
| `app_state` / inbound "settings" audit | Status feed; one-way-WS decision; dead-path removal | Audit during the wedge |
| Rokoko plugin licensing/source acceptance | Rokoko adapter `[LATER]` | Read Rokoko's open-source plugins |

## Phased build order

### Phase 0 — Documentation `[in progress]`
This spec folder. Agree architecture, scope, and open questions before code.
- [x] Architecture decided; then **inverted** to standard-stream-first + LSL-shaped (schema + samples).
- [x] Spec docs `00`–`08` written and revised to the new architecture.
- [x] This implementation plan revised.
- [ ] Final review pass with the team.

### Phase 1 — The LSL-shaped standard stream (the foundation) `[not started]`
Reshape FreeMoCap's own streaming into schema + timestamped samples; the UI is its first consumer.
- [ ] Backend **standard-stream encoder**: schema once (channels, joint hierarchy, T-pose, convention,
      units) + timestamped sample per frame; fused with the `websocket_server.py` send-path reshape.
- [ ] Canonical frame carries subject dimension, convention (in schema), confidence/reprojection error.
- [ ] Segment-rotation channel defined in the schema; the folded-in `bs/` engine produces rotations live
      (copy/adapt into SkellyForge — [11](11-kinematics-fold-in.md)). *(not blocked — we have the code)*
- [ ] UI wedge: extract message-routing + connection lifecycle from `ServerContextProvider` into a
      connection/transport service that consumes the standard stream (schema then samples).
- [ ] Tests: schema round-trip, standard-stream golden bytes, sample reconstruction.

### Phase 2 — Streaming hub + control plane + LSL route `[not started]`
- [ ] `StreamingManager` on `FreemocapApplication`; frame tap subscribes to `AggregationNodeOutputTopic`;
      latest-frame mailbox.
- [ ] `/streaming/*` router; scoped fail-loud; `stream_id` first-class; start-idle; ephemeral.
- [ ] LSL transport route (`pylsl` core dep) — near-mechanical pass-through of the standard stream.
- [ ] UI streaming controls in the Realtime UI (dropdown + modal); status via `app_state`.
- [ ] Tests: LSL pass-through via LabRecorder; mailbox drop-oldest/rate-decoupling; control-plane/failure.

### Phase 3 — VMC adapter + extract interface + finish refactors `[not started]`
- [ ] Coordinate converter + humanoid retarget derived views.
- [ ] VMC adapter ported from `freemocap_vmc/`; MTU-aware; per-socket error handling.
- [ ] Extract the adapter interface/registry (now that a transport route + a foreign adapter both exist).
- [ ] Complete the `ServerContextProvider` decomposition: **3D-data fan-out → rolling-window stores**,
      frame/canvas loop, remaining stores.
- [ ] Complete the `websocket_server.py` breakup.
- [ ] Tests: VMC golden bytes, loopback (+ cross-machine), converter vectors, one real third-party
      consumer (VSeeFace/VMC).

### Phase 4+ — Later adapters & future cleanup `[not started]`
- [ ] VRChat OSC; Rokoko JSON (pending licensing check).
- [ ] One-way-WS decision + stale-UI-after-crash reconcile.
- [ ] `[LATER]` align disabled kinematics to the new engine/models (out of hot loops until validated); retire
      only confirmed-dead `app_state`/settings fields.

## Todo (current focus)

1. Team review of this spec folder; resolve open spec-level questions.
2. Confirm the FMC canonical forward-axis and lock the convention value (goes in the schema).
3. Fold `bs/kinematics_core` into SkellyForge (copy/adapt); align existing `core/kinematics`; converge on one
   rotation implementation (assess BVH overlap).
4. During the wedge: audit `app_state` / inbound "settings" for end-to-end use; list dead paths.

## Progress log

- **2026-08-10 (consistency-pass)** — Full start-to-finish pass reconciling evolved decisions from review
  notes. Reversals/locks: **don't defer** the derived-joint-center fix — added the **`frame_offset` mapping
  form** (deterministic, anthropometric, no runtime fit) that produces the anterior clavicle SC/GH centers
  ([13](13-tracker-to-canonical-mapping.md), [12](12-standard-human-model.md)); **keep the parquet file**,
  migrate its schema to tidy-long ([10](10-serialization-and-tidy-format.md)); **align, don't delete** the
  disabled `core/kinematics` (out of hot loops until validated — [06](06-backend-refactor-and-cleanup.md));
  **timestamp is the primary time key** (frame # secondary; image data is a separate stream linked by frame #);
  `stream_id` unique vs `stream_name` label; subjects are a **sample** dimension (not a schema field);
  quaternion order **`wxyz`**; keypoint(tracker)/landmark(canonical) terminology. The "incoming SkellyModels
  code" dependency is **resolved** — it's `bs/kinematics_core`.
- **2026-08-10 (standard-human)** — Confirmed: `bs/kinematics_core` **is** the rotation/kinematics engine
  (copy/adapt, **not** import — reference only); adopt the tidy-long serialization; **VMC/VRM humanoid as
  the standard human**, rigid-body-per-bone; SkellyForge owns the model+engine, FreeMoCap holds the realtime
  variant. Agreed the **twist policy** (full-frame → chain/hinge-resolved twist → damped minimal-twist
  fallback) and the **derived-joint-center** approach (the clavicle *should* root at an anterior SC joint, not the shoulder
  midpoint / C7-T1). *(Superseded by the consistency-pass above — the anterior fix is **not** deferred; it
  uses the `frame_offset` mapping form.)* Wrote
  [12 — Standard Human Model](12-standard-human-model.md). **Open:** face blendshapes; offset magnitudes;
  VRM bone subset for v1; scapula modeling.
- **2026-08-10 (investigation)** — Investigated the overlap between SkellyModels' `Human` actor,
  FreeMoCap `core/kinematics`, and `clients/bs/python_code/kinematics_core`. Findings: the canonical
  human *model* is already SkellyModels-SSOT; the biomechanics *math* is duplicated (batch vs realtime)
  with a few misaligned hardcoded segment lists; and **`bs/kinematics_core` is a mature per-segment
  rigid-body engine (quaternion orientation + angular kinematics + tidy serialization) that appears to be
  the "segment-rotation code that lives elsewhere."** Its on-disk serialization (reference-geometry JSON +
  tidy long CSV) is the disk twin of the standard stream's schema+samples, and a cleaner format than the
  SkellyForge parquet. Wrote [09](09-standard-stream-protocol.md) (wire contract), [10](10-serialization-and-tidy-format.md)
  (serialization), [11](11-kinematics-fold-in.md) (kinematics fold-in). **Open:** confirm bs/ is the rotation
  source; adopt tidy format?; resolve the standard-human shape.
- **2026-08-10 (revised)** — Architecture **inverted** after a review pass over the first draft. New
  keystone: reshape FreeMoCap's own streaming into an **LSL-shaped standard stream** (schema once +
  timestamped samples), make it the central representation, and derive everything from it — the LSL
  route becomes a near-free pass-through, foreign adapters (VMC) derive from the standard. Also locked:
  convention/static metadata live in the **schema** not per-sample; **positive definitions only** (no
  `discarded_fields`); **`pylsl` is a core dependency**; streaming controls integrate into the
  **Realtime UI** (dropdown + modal); 3D data moves into **rolling-window stores**; `start idle`;
  **ephemeral** server-side config; SkellyModels is a module **within** SkellyForge. Build order is now
  standard-stream → LSL route/hub → VMC → later adapters. All spec docs updated. **Next:** team review;
  await incoming SkellyModels quaternion code; audit `app_state`/settings during the wedge.
- **2026-08-10 (initial)** — Architecture established and documentation set drafted. Liveness of the
  realtime path audited: pub/sub canonical frame + rigidified skeleton positions are live; the
  centroidal-kinematics path is disabled and reference-only.
