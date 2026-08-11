# Phase 1 Handoff (terse)

## Env / running
- **Use the freemocap venv for everything.** Not synced yet → `cd project/freemocap && uv sync` (heavy:
  mediapipe/onnx). Then run tests with `uv run pytest`.
- Current tests (run them): `uv run pytest freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py -q`
- Stopgap used so far (drop it once venv works): `PYTHONPATH=. ../skellycam/.venv/Scripts/python.exe -m pytest ...`
- **beartype is on package-wide** (`freemocap/__init__.py`) → keep annotations clean.
- **Never commit** (user owns git).

## Where we are
Phase 1 = reshape freemocap's own realtime stream into an **LSL-shaped standard stream** (schema once +
timestamped samples). Plans in `docs/streaming-compatibility/phase-1/`. Sequence **WS-1→WS-3→WS-2→WS-4**;
WS-5 parallel. **Done: WS-1 (contract) + WS-3 pure core (schema builder). 12 tests green.**

## Built — `freemocap/core/streaming/standard_stream/`
- `coordinate_convention.py` — `CoordinateConvention` + `FREEMOCAP_CANONICAL_CONVENTION` (mm / right / +Z;
  `forward_axis=+Y` is a **TODO/unconfirmed**).
- `stream_schema.py` — `StreamSchema` (msgspec→JSON): stream_id, stream_name, convention, `channels`
  (`ChannelGroup`: kind/names/columns/units), connections, joint_hierarchy, rest_pose, **camera_ids**.
  `ChannelKind = POINTS | ROTATIONS | OVERLAY_2D` (**no SCALARS** — CoM/xcom are POINTS). `encode/decode_schema`.
- `stream_sample.py` — binary: `SAMPLE_HEADER`(32B) + blocks(`BLOCK_HEADER` 28B + f32 rows) + footer;
  MessageType 10/11/12; POINTS cols `x,y,z,reprojection_error`; ROTATIONS `w,x,y,z`; OVERLAY_2D `x,y,visibility`
  (+ `camera_id` per block). `encode/decode_sample`. **Sizes 32/28 locked by test — the WS-4 TS decoder must match.**
- `stream_schema_builder.py` — `build_stream_schema(...)` (pure): skeleton POINTS + derived POINTS(CoM,xcom) +
  ROTATIONS(NaN until WS-5) + per-camera OVERLAY_2D.
- `lsl_bridge.py` — `schema_to_streaminfo_channels` (overlays expand × camera_ids), `sample_to_flat_vector`
  (ALL blocks — nothing excluded).
- Tests: `freemocap/tests/test_standard_stream_contract.py`, `.../test_stream_schema_builder.py`.

## Next: finish WS-3 (needs freemocap env)
1. **SkellyForge adapter** `stream_schema_from_canonical_model(...)`: pull `landmark_names`,
   `segment_connections`→(connections + segment_names), `joint_hierarchy` from
   `AnatomicalStructure.from_model_info(CanonicalBodyModelInfo()/CanonicalHandModelInfo(), "body"/"hand")`
   (`skellyforge.skellymodels.models.{anatomical_structure,tracking_model_info}`) → feed `build_stream_schema`.
   rest_pose stays empty (no rest orientations in the model yet — WS-5).
2. **Aggregator wiring**: `raw_errors_px` (already computed in
   `freemocap/core/pipeline/realtime/realtime_aggregator_node.py`) → onto `AggregationNodeOutputMessage`
   (`freemocap/pubsub/pubsub_topics.py`) as **`reprojection_error`**; add `subject_id` (=0). Positions-first:
   rotation channels stay NaN.

## Then WS-2 / WS-4 / WS-5 (see phase-1/02, 04, 05)
- WS-2: standard-stream encoder from the canonical frame + reshape `websocket_server.py` send path.
- WS-4: extract connection/transport service out of `ServerContextProvider` (TS) + decode schema/samples.
- WS-5 (parallel): copy/adapt `clients/bs/python_code/kinematics_core` INTO SkellyForge; standard-human rig;
  `anatomical_offset` mappings; twist policy; live quaternions → fill ROTATIONS.

## Load-bearing rules (do not violate)
- **LSL**: fixed channel count set at stream creation; a topology change (cameras/subjects) → **teardown+rebuild**
  (new schema). `max_persons=1` now; overlays = # connected cameras. Nothing padded/excluded.
- **Camera images = separate stream** (link by frame#). **2D overlay coordinates = in** the standard stream.
- **Timestamp is the primary key**; frame# secondary.
- **Quality naming**: 3D→`reprojection_error`, 2D→`visibility`. Never naked "confidence"/"errors".
- Rotations owned by SkellyForge — **copy `bs/kinematics_core`, do NOT import bs**. **SkellyForge NEVER imports
  FreeMoCap.** Consolidate `freemocap/core/kinematics` INTO skellyforge (align, don't delete; keep unvalidated
  code out of hot loops). skellyforge BVH exporter is **vestigial → replace/augment**.
- **Mapping** = tracker *keypoints* → canonical *landmarks* (skellytracker `*_to_canonical_mapping.yaml`; forms:
  string / list-mean / dict-weighted + new **`anatomical_offset`** for off-surface joint centers, e.g. the
  clavicle SC — anthropometric, deterministic, no runtime fit). **No "virtual markers."**
- `msgspec` for schema; **two-word file names**; docstrings use explicit markdown doc-links.

## Spec index
`docs/streaming-compatibility/README.md` → 00–13 + `IMPLEMENTATION_PLAN.md` + `phase-1/`.
