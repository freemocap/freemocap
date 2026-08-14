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

## Agreed architecture

Settled in discussion 2026-08-12. These are decisions, not options.

### A1 — Compose what we author; generate the flat skeleton

A hand has 15 segments. A human has two hands. The flat form writes all 30 finger segments out
explicitly (`left_thumb_metacarpal`, `right_thumb_metacarpal`, …) and the hand-as-a-unit exists nowhere.
The composed form writes the hand **once**, side-agnostic, and the human says "a hand at each wrist."

**We author the composed form.** The flat segment list is *generated at load time*. Writing the hand's
structure twice is duplicated information, and no information is duplicated.

The current 55-segment alias table is precisely the forbidden shape: **30 of its 55 entries are fingers,
15 left and 15 right**, the same structure stated twice.

Nothing downstream changes shape — the orientation solver and the stream schema still receive one flat,
indexed segment list. They receive it from a build step instead of from a file. Building once at load is
also where the per-frame O(n) lookups (**D13**) stop being O(n²).

### A2 — Parts join by name agreement; there is no attachment mechanism

Everything kinematic is defined as connected segments in **one** joint hierarchy.

A part is authored with local landmark names. The hand's root landmark is `wrist`. Instantiating it with
the prefix `left_` makes that `left_wrist` — which is already the body's wrist landmark, so they are the
same node. Parts join because their names coincide after prefixing.

There is deliberately **no** separate "attachment point" concept, no gluing step, and no notion of parts
overlapping or abutting. Composition is an authoring convenience that expands into the single tree; once
expanded there is nothing left over to get wrong.

Twist-policy references resolve under the same prefix rule: the hand part naming `lower_arm` as a twist
source becomes `left_lower_arm` in the left instance.

### A3 — Mirroring: reflect positions, rebuild frames

The two hands share topology; their rest geometry is mirrored.

In the canonical convention (`+X` forward, `+Z` up, right-handed) the sagittal plane is the XZ plane, so
**mirroring negates Y** — `+Y` is the subject's left, since `Y = Z × X`.

**The rule, and it is not optional:**

1. Reflect the **rest positions** (negate Y).
2. **Rebuild** each segment's coordinate frame from the reflected positions using the ordinary
   right-handed construction — exact axis, approximate axis, third by cross product.
3. **Never reflect a basis, rotation matrix, or quaternion directly.**

Reflection has determinant −1. Mirroring a frame directly yields a left-handed frame, which silently
breaks every construction that assumes right-handedness — including `anterior = up × lateral`, the thing
that makes the sternoclavicular offset anterior rather than posterior
([07](../07-coordinate-conventions.md#subject-relative-constructions)). Rebuilding from mirrored positions
gives a proper right-handed frame by construction.

**Guard:** assert `det(basis) == +1` for every segment on **both** sides after composition — added to
[14 §7](../14-engine-testing-strategy.md#7-standard-human-model).

### A4 — The face is a different kind of thing

Body and hands are segment chains with a joint hierarchy. The face is 52 expression weights — no segments,
no hierarchy, no kinematics.

So the standard human is **not** a uniform bag of parts. It is a skeleton (composed of segment-chain parts)
**plus** an expression set. Those compose together into one human without being forced into a shared
abstraction. Per the rule: what is kinematic is defined kinematically; what is not is defined on its own.

### A5 — One human per `StandardHuman`

`StandardHuman` describes exactly one human. Multiple subjects are a **list of humans** — the model has no
multi-subject dimension and must not grow one. The stream's subject dimension
([01](../01-canonical-data-model.md#multi-subject-from-day-one)) indexes such a list; it does not reach
into the model.

### A6 — The model layer knows nothing about trackers

`Aspect` currently does two unrelated jobs: it is a body part **and** a slice of a tracker's output array
(`add_tracked_points_numpy(arr[:, tracked_point_slices[...], :])`). That second job is why the layer is
tracker-flavoured and why `tracker_name: canonical` exists at all.

The array-slicing job is deleted. Keypoint→landmark is owned by skellytracker's mapping YAMLs
([13](../13-tracker-to-canonical-mapping.md)); trajectory data attaches to the resolved skeleton by
landmark name. **SkellyForge's model describes a person, not a detector.**

### A7 — Composition replaces the manager inheritance

`Actor → Human / Animal / Board` is inheritance encoding a parts list — `Human` exists to "add support for
face, left_hand and right_hand aspects." Under composition a human *is* its parts list and an animal is a
different one, so the subclasses and their duplicated `add_tracked_points_numpy` overrides go away.

### What the segment definition looks like

One definition owns everything about an edge — endpoints, length ratio, and (as the standard human absorbs
it) reference geometry and twist policy:

```yaml
name: canonical_hand          # authored ONCE; instantiated per side
root_landmark: wrist          # unifies with the body's {prefix}wrist

landmarks: [wrist, thumb_metacarpal, thumb_proximal, ...]

segments:
  thumb_metacarpal:
    proximal: wrist
    distal: thumb_proximal
    length_ratio: 0.015       # of stature — never an absolute distance
```

- **No string parsing.** `split("->")` and both call sites disappear; endpoints are fields.
- **One place to change an edge.** The failure that opened this workstream becomes impossible.
- **Hierarchy is derived**, so it cannot drift from the segments.
- **Lengths stay body-scaled** — ratios of stature, or of a named reference length for offsets.

## Open questions

- **F4 scope.** Rewriting `models/` + `managers/` onto this architecture has posthoc-pipeline blast radius.
  Does it land in SF-AL, or does SF-AL stop at the data model (F1–F3, F5) and hand F4 its own plan?
- **F6 boundary.** Which FreeMoCap files are genuinely FreeMoCap's (realtime orchestration, I/O, pipeline
  wiring) versus SkellyForge's (skeleton math)? The rigidifier is a wrapper and wrappers may legitimately
  stay.
- **Two CoM implementations** — which is authoritative? The FreeMoCap one is 6× larger and is what the
  realtime path uses.
- **Alias authoring.** `BONE_ALIASES` has the same 15+15 finger duplication. Aliases could be authored
  per-part and prefixed like everything else, but VRM's names are camelCase (`leftThumbMetacarpal`) rather
  than mechanically prefix-derived, so the rule needs stating.

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
