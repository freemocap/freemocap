# SF-AL — SkellyForge Alignment

> **The gap this closes.** The canonical human data model was redesigned around **VRM 1.0 segments**
> ([12](../12-standard-human-model.md)) and a strict keypoint/landmark/segment vocabulary
> ([13](../13-tracker-to-canonical-mapping.md)). `canonical_body.yaml` and its consumers **predate that
> work** and were never brought forward. Separately, the "all skeleton-building code lives in SkellyForge"
> consolidation is **partially done** — stragglers remain in FreeMoCap.
>
> The result is two disconnected human models in one repo, three encodings of one skeleton graph, and a
> byte-identical dead package.
>
> **Status: plan for agreement — no code until agreed.**
>
> Discovered while implementing D7/D8 (bilateral sternoclavicular). That work is **paused mid-flight** —
> see [Work in flight](#work-in-flight) before touching the model.

## Why this is a workstream and not a cleanup

The trigger was cosmetic — arrow-delimited dict keys — but the survey found the arrow is a symptom.
Every item below is a place where SkellyForge still describes a human the way it did *before* the standard
human existed.

**The proof that redundancy is already costing us:** rerooting the clavicle onto the SC joints required
editing `segment_connections`, `bone_length_ratios` **and** `joint_hierarchy`. Two were updated, one was
missed, and the model silently became self-inconsistent (`joint_hierarchy` still routes
`neck_center → left_shoulder`). Nothing failed. Nothing could have failed — no single place owns that edge.

## Findings

### F1 — One skeleton graph, three encodings, already disagreeing

`canonical_body.yaml` describes the same directed graph three times:

| Encoding | Size | Form |
|---|---|---|
| `segment_connections` | 25 segments | `name → {proximal, distal}` |
| `bone_length_ratios` | 28 keys | `"proximal->distal" → ratio` — **a string that must be parsed** |
| `joint_hierarchy` | 26 edges | `parent → [children]` |

Measured overlap and disagreement:

- **20 edges** described twice, **16** described three times
- **8** ratio edges have no matching segment
- **5** segments have no ratio
- **10** hierarchy edges have no matching segment

### F2 — Structured data encoded in strings

`bone_length_ratios` keys are parsed with `bone_key.split("->", 1)` at two sites:
`skellyforge/kinematics/online_segment_lengths.py:56` and
`freemocap/core/tasks/mocap/rigid_body/online_segment_lengths.py:51`. The key is built by a helper in
`segment_lengths.py:49` documented as *"Key into bone_length_ratios (parent->child)"*.

Same anti-pattern in `managers/actor.py:303`: `tracker_name, aspect_name = model_name.split(".")` — the
dotted-string hierarchy [10](../10-serialization-and-tidy-format.md) already flags as a pain point in the
parquet schema.

### F3 — Pre-standard-human vocabulary

`canonical_body.yaml` declares `tracker_name: canonical` — asserting the canonical model's tracker is
"canonical", which denotes nothing — and calls its landmarks `tracked_points`, the vocabulary
[13](../13-tracker-to-canonical-mapping.md) replaced. Landmarks are *fitted*; "tracked point" says
measured.

### F4 — Two disconnected human models in one repo

`skellymodels/models/` + `skellymodels/managers/` (~1,500 lines: `AnatomicalStructure`, `ModelInfo`,
`Aspect`, `Trajectory`, `Actor`, `Human`, `Animal`, `Board`) contain **zero references** to
`skellymodels/standard_human/`. They are parallel, not layered. Locked decision 3 in
[standard-human-model](standard-human-model/README.md) called for rewriting them onto the standard human;
that has not happened.

### F5 — A byte-identical dead package

`skellyforge/biomechanics/` duplicates `skellyforge/skellymodels/biomechanics/` — all 7 files compare
**identical**. Only the `skellymodels/` copy is imported (by `managers/actor.py`). The top-level copy is
unreachable.

### F6 — Realtime/posthoc consolidation incomplete

Skeleton-building code still living in FreeMoCap that belongs in SkellyForge:

| FreeMoCap file | Lines | Note |
|---|---|---|
| `core/tasks/mocap/center_of_mass.py` | 393 | A **second** CoM implementation; SkellyForge has `calculate_center_of_mass.py` |
| `core/tasks/mocap/rigid_body/skeleton_rigidifier.py` | 319 | Realtime wrapper over SkellyForge's `TreeRigidifier` (136) — the wrapper may be legitimately FreeMoCap's, but the split needs stating |
| `core/tasks/mocap/rigid_body/online_segment_lengths.py` | 98 | Near-duplicate of SkellyForge's (116); reachable only from one test |
| `core/tasks/mocap/mocap_helpers/skeleton_from_mediapipe_observations.py` | 144 | Skeleton construction |
| `core/tasks/mocap/segment_length_io.py` | 236 | I/O around SkellyForge's segment-length math |
| `core/tasks/mocap/streaming_kinematics.py`, `body_kinematics_state.py` | 133 | Disabled centroidal path (`[LATER]`, [06](../06-backend-refactor-and-cleanup.md)) |

### F7 — Cross-repo rule violations (known, still open)

`data_models/observation.py` and `pipelines/dlc_pipeline.py` import from **skellytracker**. Both are
`TYPE_CHECKING`-only so they don't bind at runtime, but the rule is *"sub-skellies never import from each
other or from FreeMoCap"* and these are the standing exceptions.

## The target shape

**One segment definition owns everything about an edge.** Endpoints, length ratio, and — when the standard
human absorbs it — reference geometry and twist policy:

```yaml
name: canonical_body

# The landmark the skeleton tree is rooted at. joint_hierarchy is DERIVED from
# `segments` given this root, never stated separately.
root_landmark: hips_center

landmarks:
  - nose
  - left_shoulder
  # ...
  - left_sternoclavicular
  - right_sternoclavicular

segments:
  left_shoulder:                      # VRM leftShoulder — the clavicle
    proximal: left_sternoclavicular
    distal: left_shoulder
    length_ratio: 0.1094              # of stature
```

Properties this buys:

- **No string parsing.** `split("->")` and its two call sites disappear; a segment's endpoints are fields.
- **One place to change an edge.** The failure that started this workstream becomes impossible.
- **Derived hierarchy cannot drift**, because it is a computed property, not stored data.
- **Ratios stay body-scaled.** All lengths remain ratios (of stature, or of a named reference length for
  offsets) — never absolute distances, which would silently assume one body size.

## Open questions

- **F4 is the big one.** Rewriting `models/` + `managers/` onto the standard human is a large change with
  a posthoc-pipeline blast radius. Does it land in this workstream, or does SF-AL stop at the data model
  (F1–F3, F5) and hand F4 to its own plan?
- **F6 boundary.** Which of the FreeMoCap files are genuinely FreeMoCap's (realtime orchestration, I/O,
  pipeline wiring) versus SkellyForge's (skeleton math)? The rigidifier in particular is a wrapper, and
  wrappers may legitimately stay.
- **Two CoM implementations** — which is authoritative? The FreeMoCap one is 6× larger and is what the
  realtime path uses.

## Task checklist

Ordered so each step leaves the tree consistent.

1. [ ] **Agree the target shape above**, and record the decisions in
       [12](../12-standard-human-model.md) / [13](../13-tracker-to-canonical-mapping.md).
2. [ ] **Delete `skellyforge/biomechanics/`** (F5) — unreachable, byte-identical.
3. [ ] **Restructure `canonical_body.yaml`** to `landmarks` + `segments` + `root_landmark` (F1, F3).
4. [ ] **Derive `joint_hierarchy`** from `segments`; delete the stored copy.
5. [ ] **Update consumers**: `AnatomicalStructure`, `ModelInfo`, `segment_lengths.py`,
       `online_segment_lengths.py`, `skeleton_rigidifier.py` (both repos) — remove all `->` parsing (F2).
6. [ ] **Resolve the `online_segment_lengths` duplicate** (F6) — one implementation in SkellyForge.
7. [ ] **Decide and act on the CoM duplication** (F6).
8. [ ] **Tests** — model-integrity tests per [14](../14-engine-testing-strategy.md) §7: every segment's
       endpoints exist in `landmarks`; the graph is a single-rooted tree; every segment has a ratio; no
       segment has coincident endpoints.
9. [ ] **F4 scope decision**, then execute or hand off.

## Work in flight

**D7/D8 (bilateral sternoclavicular) is paused part-way** and must be finished or reverted before the
restructure, so it isn't half-carried into the new shape. Landed so far:

- `left_sternoclavicular` / `right_sternoclavicular` in **both** tracker mappings, verified identical
  across RTMPose and MediaPipe, and verified scale-invariant (0.0396 H at every stature, tracking
  biacromial ratio correctly).
- **D39 fixed** in `tracker_mapping.py`: an offset naming an axis outside its frame used to `continue`,
  silently contributing nothing and yielding a plausible-but-wrong landmark. It now raises. An ambiguous
  third-axis inference also raises.
- `canonical_body.yaml`: both landmarks added; `segment_connections` rerooted onto the SC joints;
  `bone_length_ratios` derived **symbolically** from the offset definition rather than via millimetres for
  an assumed 1.7 m subject.

**Not yet done:** `joint_hierarchy` still routes `neck_center → left_shoulder` (the inconsistency in F1);
`_BONE_TO_LANDMARK` in the FreeMoCap aggregator still roots the clavicle at the shoulder keypoint;
[12](../12-standard-human-model.md) still specifies a **singular** SC joint and needs revising to bilateral.
