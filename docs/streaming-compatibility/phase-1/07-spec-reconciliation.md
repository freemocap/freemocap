# FMC-SR — Spec Reconciliation (SF-SH-6)

> **Build order: now, before any further code.** Realizes the follow-up actions from
> [`AUDIT_2026-08-12`](../AUDIT_2026-08-12.md). This is SF-SH-6 — the "update the specs" workstream listed
> as *continuous* in [`standard-human-model/`](standard-human-model/README.md) that never ran, and which the
> audit identified as the root cause of nearly every drift item.
>
> **Status: plan for agreement — no code until agreed.**
>
> **This pass is documentation only.** No source files in any repo are touched. The engine tests specified
> in §5 are *specified* here and *written* in a later pass.

## Why this exists

Three things happened at once and none of them reached the specs:

1. The build sequence was reversed (positions-first → canonical-model-first) for a good reason that was
   recorded in exactly one file.
2. The vocabulary drifted. "Keypoint", "landmark", "bone", and "segment" are used inconsistently across
   `00`–`13`, and the executable plan in [`03`](03-canonical-frame-extensions.md) quietly overrode
   [`09`](../09-standard-stream-protocol.md) on what the channel groups enumerate.
3. New requirements arrived (everything on the wire; landmark reprojection into the 2D overlays) that no
   doc describes yet.

Every downstream workstream — FMC-WS-2's encoder, FMC-WS-4's decoder, FMC-RB's renderer — hardcodes a
block layout against decisions that are currently stated three different ways. Fixing the specs first is
cheaper than fixing three implementations later.

---

## 1. Terminology — the load-bearing fix

**The distinction, stated once and authoritatively.** There are **two kinds of 3D trajectory**, and they
mark the boundary between the two repos:

| Term | What it is | Produced by | Repo |
|---|---|---|---|
| **Keypoint trajectory** | A point tracked in 2D by a detector and triangulated to 3D. Tracker-specific names. Raw observation. | detectors → triangulation | **SkellyTracker** |
| **Landmark trajectory** | The 3D trajectory of a specific feature **on a segment** of the model we fit to the keypoints. A landmark is *a point on a segment* (e.g. greater trochanter) — its segment attachment is intrinsic, not incidental. | model fitting | **SkellyForge** |
| **Segment** | A 3D-oriented rigid body of the fitted model. Carries landmarks and an orientation. | model fitting | **SkellyForge** |

**The handoff is the `*_to_canonical_mapping.yaml` files in SkellyTracker**: keypoints in, landmarks out.
That is the entire interface between the two repos, and it is the reason this vocabulary has to be exact.

### 1a. Segments, not anatomical bones (current scope)

We are **not** currently working at the level of anatomical bones. We are fitting **3D-oriented segments**
matched to the **VRM 1.0** schema — the level of abstraction that streaming formats like VMC operate at,
and the level the 3JS mesh renderer ([`06`](06-rigid-body-bone-renderer.md)) draws. Anatomically-aligned
bone models come **`[LATER]`**.

This directly qualifies locked decision 3 in [`standard-human-model/`](standard-human-model/README.md)
("Bones subsume segments"). That decision stands as a *structural* claim — one rigid body per segment,
carrying its own reference geometry — but the entities are **VRM-aligned segments**, not anatomy. The
`HumanBone` / `human_bones.py` / `BONE_ALIASES` names in code are VRM's vocabulary, not a claim about
skeletal anatomy, and the docs must say so or the next reader will assume more precision than exists.

### 1b. The strategic frame, stated plainly

The near-term deliverable is an **LSL-shaped streaming backbone carrying VMC-compatible segment data.**
The actual LSL outlet and VMC socket are **later** — they are near-mechanical once the backbone and the
data shape are right. [`00`](../00-overview.md) implies this; it should say it.

### Tasks

1. [x] **[`00`](../00-overview.md) § Glossary** — split into "the four load-bearing terms" (keypoint
       trajectory / landmark trajectory / segment / mapping, marked as quick-reference deferring to `13`)
       and "streaming terms". Corrected the `Schema` and `Segment quaternion` entries.
2. [x] **[`13`](../13-tracker-to-canonical-mapping.md)** — retitled *Keypoint → Landmark Mapping*; declared
       the **SSOT for the distinction**; added § *Two kinds of trajectory* (measured vs. fitted, with the
       `left_elbow` keypoint-vs-landmark illustration) and the boundary diagram showing the mapping files as
       the entire interface.
3. [x] **[`12`](../12-standard-human-model.md)** — added § *Segments, not anatomical bones* as the first
       section, qualifying locked decision 3.
4. [x] **[`00`](../00-overview.md) § The goal** — added § *Backbone first, endpoints later*.
5. [x] Vocabulary sweep of `01`–`13`. Fixed: `01` (per-segment directions; rest-pose identity was written
       `(0,0,0,1)` — **xyzw, wrong for this codebase** — now `(1,0,0,0)` wxyz), `07` (`rotation_frame` row,
       flagged under revision), `08` (segments' world positions), `11` (landmark set on segments, canonical
       model, rigid-segment step), `12` (landmarks not "markers" throughout). Remaining "bone" uses in
       `02`/`03`/`07` are **foreign-protocol vocabulary** (VMC/VRM/Unreal bone-name maps) and are correct as
       written.

---

## 2. Channel groups — resolve the 09-vs-03 conflict

**Decision: the stream carries everything.** It is all small data; adapters subset. This follows
[`01`](../01-canonical-data-model.md)'s superset principle, and settles the audit's
[§2.1](../AUDIT_2026-08-12.md#21-landmark-vs-bone-the-specs-contradict-each-other).

Target channel groups — **the measured half and the reconstructed half**:

| # | Group | Names are | Columns |
|---|---|---|---|
| 0 | `KEYPOINTS_3D` | tracker keypoint names | `x, y, z, reprojection_error` |
| 1 | `SEGMENT_ORIGINS` | segment names — **transform origin (proximal joint)**, not midpoint | `x, y, z` |
| 2 | `ROTATIONS_LOCAL` | segment names | `w, x, y, z` |
| 3 | `ROTATIONS_WORLD` | segment names | `w, x, y, z` |
| 4 | `DERIVED_POINTS` | `center_of_mass`, `xcom` | `x, y, z` |
| 5… | `OVERLAY_2D` | per camera × layer — see §3 | `x, y, visibility` |

**Landmarks are not on the stream.** The current work is the **segment** layer of the data model; a landmark
(a named anatomical feature riding on a segment) is `[LATER]`, possibly never on the wire. Adding a third
point set before it is needed would be speculative wire surface.

**Shape chosen for VMC.** VMC's model is a root transform plus per-bone **local** rotations, with child
placement coming from the rest pose composed through the rotation chain. `SEGMENT_ORIGINS` carries transform
origins (which is what a VRM/VMC bone position *is*), `ROTATIONS_LOCAL` is the rotation contract, and
`rest_pose` + `segment_parents` are in the schema — so the VMC adapter is a name map plus a convention
conversion, with nothing to reconstruct. Both rotation frames stay first-class per locked decision 5; the
3JS renderer and world-space analysis consumers take `ROTATIONS_WORLD`.

### Tasks

1. [x] **[`09`](../09-standard-stream-protocol.md) § channels** — rewritten against the six-group table and
       declared **the single authority** on channel content. Added the keypoint-vs-landmark distinction as
       first-class (both carried, both named honestly), one `block_kind` per group, and `overlay_layer` in
       the block header. Status header corrected to "partly implemented".
2. [x] **[`03`](03-canonical-frame-extensions.md)** — inline enumeration replaced by a deferral to `09`,
       with an explicit note that this file *became* the de-facto authority by accident and that is what
       produced the conflict. Checklist re-opened for the items that landed against the old layout.
       **The same SSOT bug was found in two more plans** and fixed identically:
       [`02`](02-backend-encoder-and-ws-reshape.md) (sample-builder block order) and
       [`04`](04-ui-wedge.md) (TypeScript `ChannelKind`) both carried competing definitions.
3. [x] **[`01`](../01-canonical-data-model.md) § what the frame carries** — table rewritten with a
       **Channel group** column mapping each frame field to its `09` group; keypoint and landmark
       trajectories now separate rows with measured-vs-fitted stated.
4. [x] **[`09`](../09-standard-stream-protocol.md)** — `segment_parents` declared as a schema field; with
       `rest_pose` it is what lets a consumer compose the local-rotation chain into world placement, which
       is the VMC/VRM model. Added a **"Why this shape maps onto VMC"** table showing the adapter reduces to
       a name map + convention conversion.
5. [x] **[`09`](../09-standard-stream-protocol.md) § open questions** — stale subject-count bullet deleted;
       resolved items moved into the body with a pointer left behind. Only `nominal_srate` remains open,
       now with a trigger.
6. [x] **[`07`](../07-coordinate-conventions.md)** — `rotation_frame` dropped from the convention tuple in
       `09`'s schema table; both frames ship as distinct channel groups, so the field described nothing.

---

## 3. 2D overlays carry both detections and reprojections `[NEW]`

**New requirement, not yet in any doc.** Each camera's `OVERLAY_2D` must carry **two layers**:

- the **original tracker keypoints** as detected in that camera's image, and
- the **reprojected landmarks/segments** — the fitted 3D model projected back down into that camera.

This makes fit quality directly visible per camera: detected vs. fitted, overlaid. It is the cheapest
validation instrument available for the whole fitting pipeline, and it costs almost nothing on the wire.

**Camera parameters are not an open question.** If we are reconstructing 3D at all, we know the camera
info by definition — reprojection pulls intrinsics + extrinsics from the **existing camera calibration
infrastructure** (the same calibration the triangulator already consumes, hot-reloaded by the aggregator).
No new source, no new dependency; wire it up when we reach the implementation pass.

### Tasks

1. [x] **[`09`](../09-standard-stream-protocol.md)** — **decided: one `OVERLAY_2D` kind with an
       `overlay_layer` discriminator** (`DETECTIONS` | `REPROJECTIONS`) in the block header, alongside
       `camera_id`. Two kinds would have duplicated the per-camera keying logic for no gain. A `C`-camera
       rig sends `2C` overlay blocks per sample.
2. [x] **[`01`](../01-canonical-data-model.md)** — reprojected landmarks added to the frame table as an
       `OVERLAY_2D` row, with the residual-vs-fit rationale.
3. [x] **[`09`](../09-standard-stream-protocol.md)** — records that reprojection reads the existing
       calibration, and that a calibration change rebuilds the stream with a new schema exactly as it
       invalidates triangulation.
4. [ ] **[`05`](../05-ui-integration-and-refactor.md)** — the UI needs a per-layer visibility toggle;
       note it.
5. [ ] **[`02`](02-backend-encoder-and-ws-reshape.md)** — landmark reprojection is **new encoder scope**;
       flagged in its header, needs its task checklist updated.

---

## 4. Sequencing record + FMC-WS-5 absorption

Per [`AUDIT_2026-08-12` §1](../AUDIT_2026-08-12.md#1-the-sequencing-reversal--correct-decision-incompletely-recorded)
and [§1a](../AUDIT_2026-08-12.md#1a-fmc-ws-5-and-the-standard-human-sub-plan-are-two-plans-for-the-same-work).

### Tasks

1. [ ] **[`phase-1/README.md`](README.md)** — replace the "Key sequencing decision — DECIDED: (A)
       positions-first" block with the decision as actually taken: dated 2026-08-11, with the reason (the
       stream shape can't be designed without the data that flows through it), marked as **superseding** the
       original rather than silently rewritten.
2. [ ] **[`phase-1/README.md`](README.md) § definition of done** — fix the "rotations declared-NaN or
       populated live" bullet; rotations are live, the encoder is the open half.
3. [ ] **[`phase-1/README.md`](README.md) § Status** — check the boxes that are done.
4. [ ] **Absorb `05-kinematics-foldin-rotations.md` into [`standard-human-model/`](standard-human-model/README.md)**,
       then delete it. Only two parts have no SF-SH equivalent and must be carried over: sub-item **5f**
       (consolidate `core/kinematics`; point `LIMB_SEGMENTS` / `_SEGMENT_CHAINS` at the canonical model) and
       the "Not in scope (Phase 1)" list.
5. [ ] **[`phase-1/README.md`](README.md) § Workstreams table** — FMC-WS-5 row points at
       `standard-human-model/`.
6. [ ] **[`IMPLEMENTATION_PLAN`](../IMPLEMENTATION_PLAN.md)** — reconcile the two ID namespaces
       (`FMC-WS-n` vs `SF-SH-n`/`ST-SH-n`) in the Phase 1 checklist and "Todo (current focus)".

---

## 5. Engine testing strategy — a new spec doc

[`08`](../08-testing-strategy.md) covers the wire and nothing owns the math
([`AUDIT_2026-08-12` §2.3](../AUDIT_2026-08-12.md#23-the-plans-have-no-testing-strategy-for-the-skellyforge-engine)).
SkellyForge has no test infrastructure at all.

**New doc: `14 — Engine Testing Strategy`**, sibling to `08`, cross-linked both ways. `08` keeps its tight
"the wire is unforgiving" thesis; `14` owns the math.

Content to specify (not write):

- **Quaternion algebra** — Hamilton product associativity/non-commutativity, conjugate-inverse identity,
  `from_rotation_matrix` round-trip across all four Shepperd branches, SLERP endpoints + shortest-arc.
- **Composition convention** — the decisive one: a **differential** parent/child case (different axes,
  different magnitudes) plus a `recompose(parent, local) == child` round-trip. Per
  [`AUDIT_2026-08-12` §3.1](../AUDIT_2026-08-12.md#31-local-quaternion-composition-order), the existing
  uniform-bend check is structurally unable to detect operand-order errors and must not be the only case.
- **Basis + Kabsch** — orthonormality, right-handedness, exact and noisy recovery, near-parallel rejection.
- **Orientation solver** — identity-at-T-pose, per-tier dispatch, singularity-gate crossing, damping
  behaviour over a frame sequence.
- **`anatomical_offset`** — determinism, subject-scaling linearity, correct sign given a declared
  forward-axis.
- **Test infrastructure** — `skellyforge/tests/`, pytest config, and the fact that skellyforge changes
  verify in skellyforge's own env and are invisible to freemocap until committed.

### Tasks

1. [x] Wrote [`14-engine-testing-strategy.md`](../14-engine-testing-strategy.md), covering §1–7 plus the
       missing test infrastructure. Its organizing rule: **a test must be able to fail for the reason it
       exists** — with the uniform-bend case named as the cautionary example, and a closing requirement that
       no test may pass under both operand orders, both handedness conventions, or both component orders.
2. [x] Cross-linked: [`08`](../08-testing-strategy.md) retitled "(the wire)" with an explicit scope boundary,
       [`11`](../11-kinematics-fold-in.md) points at 14 and its status corrected to "executed",
       [`README`](../README.md) table gains row 14 and marks 08 as the wire's doc.
3. [x] Suite added to [`IMPLEMENTATION_PLAN`](../IMPLEMENTATION_PLAN.md) `[IN]` scope, with the ordering
       constraint that §2's tests land **before** the composition fix.

---

## 6. Specify critical damping concretely

**Decision: implement real critical damping.** [`12`](../12-standard-human-model.md) and `TwistPolicy`'s
docstring both say "critically damped"; the code is a first-order lag. The word is the intent — so the spec
must define it precisely enough to implement.

### Tasks

1. [x] **[`12`](../12-standard-human-model.md) § Critical damping — specification** added: second-order,
       damping ratio 1, per-segment angular-velocity state carried across frames. Records why a first-order
       lag cannot substitute (it never overshoots but cannot settle quickly, trading pop for lag).
2. [x] **Fallback-path requirement specified** — damping must apply when the twist source is occluded *and*
       when the singularity gate trips, which is the case it exists for (defect D3).
3. [x] **`damping_factor` → time constant in seconds.** The load-bearing part: a per-frame blend factor
       silently means different things at 30/60/120 fps, so a rig tuned on one machine misbehaves on
       another. Framerate independence is asserted by [14 § critical damping](../14-engine-testing-strategy.md#5-critical-damping).
4. [x] First-frame, after-gap, and reset behaviours specified; state ownership pointed at defect D16.

---

## 7. World-quaternion direction convention

Currently inferable from three docstrings and stated in no doc — yet it determines the parent-relative
composition and what the Phase-3 VMC adapter must do.

### Tasks

1. [ ] **[`07`](../07-coordinate-conventions.md)** — state the convention explicitly: does `q_world` map
       segment-frame → world, or world → segment frame? Write the parent-relative composition formula that
       follows from it.
2. [ ] Record it in [`IMPLEMENTATION_PLAN`](../IMPLEMENTATION_PLAN.md) § Dependencies & blockers as
       resolved once stated.

---

## 8. Status headers and stale facts

Mechanical sweep, from [`AUDIT_2026-08-12` §5](../AUDIT_2026-08-12.md#5-smaller-doc-vs-reality-items).

### Tasks

1. [ ] [`README`](../README.md) status line — "Nothing here is implemented yet" is false.
2. [ ] Status headers on [`09`](../09-standard-stream-protocol.md), [`11`](../11-kinematics-fold-in.md),
       [`12`](../12-standard-human-model.md).
3. [ ] [`06`](../06-backend-refactor-and-cleanup.md) — three dead `core/kinematics/` paths.
4. [ ] [`HANDOFF`](HANDOFF.md) — file map (`stream_schema_builder.py` retired), Uncommitted list,
       "deleted" → "moved", 12 → 23 tests.
5. [ ] [`01`](01-standard-stream-contract.md) section headers — `schema.py`/`sample.py` →
       `stream_schema.py`/`stream_sample.py`.
6. [ ] [`03`](03-canonical-frame-extensions.md) — check the 6 done checklist items; drop `frozen=True` from
       the interface block (code is not frozen) or record it as a required change.

---

## 9. Evaluation of FMC-RB (the 3JS segment renderer)

[`06-rigid-body-bone-renderer.md`](06-rigid-body-bone-renderer.md), evaluated as requested.

**The design is right.** The elliptical cross-section is the strongest idea in it: a circular cone looks
identical at every roll angle, so a symmetric mesh would make the twist policy — the hardest and least
verifiable part of the orientation solve — invisible. Squishing local X turns the viewport into the
validation instrument for §6's damping and the twist tiers. Single `InstancedMesh`, scratch reuse,
zero-alloc hot path, and separation from the tracker keypoint/connection layers are all correct and match
the keypoint-vs-landmark boundary in §1.

**One thing it cannot do, and the plan should say so.** The renderer is driven by `ROTATIONS_WORLD`.
The audit's [§3.1](../AUDIT_2026-08-12.md#31-local-quaternion-composition-order) bug is in
`ROTATIONS_LOCAL`. **A correct-looking viewport will therefore not catch it** — the exact failure
[`08`](../08-testing-strategy.md) warns about ("a receiver you wrote yourself shares your
misconceptions"). Local rotations need a test, not a look.

**Four concrete defects in the plan, to fix while specs are open:**

1. **`buildBoneInstances()` loses segments.** It sets `boneName = parentName` and does `map.set(boneName, …)`
   once per hierarchy *edge*. Any parent with multiple children — `hips` → `spine`, `left_upper_leg`,
   `right_upper_leg` — writes the same key three times, last-write-wins, and two legs vanish. Segments are
   first-class and named in the schema; index them directly instead of deriving a name from an edge.
2. **Cross-section scales with segment length.** `_scl.set(SQUISH_X * length, SQUISH_Y * length, length)`
   makes a femur fat and a toe skinny. Cross-section should come from a radius parameter (or an
   anthropometric ratio), independent of long-axis length.
3. **O(n²) in the hot path.** `rotations.boneNames.indexOf(boneName)` is a linear scan per segment per
   frame, inside a plan that is otherwise careful about allocation. Resolve to an index once when the schema
   arrives, exactly as `proximalFrameIdx` already is.
4. **`setColorAt` every frame.** Colour is static per instance; set it once at schema time.

### Tasks

1. [ ] Fix defects 1–4 in [`06`](06-rigid-body-bone-renderer.md).
2. [ ] Add the "this renderer cannot validate `ROTATIONS_LOCAL`" note, cross-linked to `14`.
3. [ ] Update its data-source table to §1's vocabulary (segments, landmarks) and §2's channel groups.
4. [ ] Add the §3 overlay layers to the viewport visibility toggles alongside `rigidBodyBones`.

---

## 10. Defect register — everything found, nothing deferred

Every defect the audit surfaced, with its fix. **No item is deferred and no item is "acceptable for now."**
Column *Pass* says which pass fixes it: **SR** = this documentation pass, **CODE** = the code pass that
immediately follows it (spec-first is a sequencing rule, not a deferral — every CODE row has its target
written by an SR row above it).

### 10a. Correctness

| # | Defect | Fix | Pass |
|---|---|---|---|
| D1 | `orientation_solver.py:366` composes parent-relative rotation as `world * conj(parent)`; the convention requires `conj(parent) * world`. `ROTATIONS_LOCAL` is wrong for any segment whose parent is rotated — and that is what VMC consumes. | State the convention (§7), write the differential-bend + round-trip test (§5), then correct the composition. | SR → CODE |
| D2 | The SF-SH-4 test that "passed" used a **uniform** bend, where `q_child == q_parent` and both operand orders collapse to identity. It cannot detect D1. | §5 mandates a differential case + `recompose(parent, local) == child`. Delete or supersede the uniform-only check — it is worse than no test, because it reads as coverage. | SR → CODE |
| D3 | `_solve_chain_resolved` passes `previous_world_quaternion=None` on both fallback paths, so damping is skipped in exactly the occlusion/singularity case it exists for. | §6 task 2 specifies that damping must apply on fallback paths. | SR → CODE |
| D4 | Damping is a first-order lag (95% previous frame, ~0.33 s time constant at 60 Hz) but documented as "critically damped" in [`12`](../12-standard-human-model.md) and `TwistPolicy`. | §6: implement real critical damping — second-order, per-segment angular-velocity state, damping expressed as a **time constant in seconds** so it is framerate-independent. | SR → CODE |
| D5 | `buildBoneInstances()` in [`06`](06-rigid-body-bone-renderer.md) keys segments by `parentName`, so a parent with N children writes one map entry N times — `hips` silently drops both legs. | §9 task 1: index segments by their schema-declared names, not by hierarchy edges. | SR |
| D6 | Renderer cross-section scales with segment length (`_scl.set(SQUISH_X * length, SQUISH_Y * length, length)`) — fat femurs, skinny toes. | §9 task 1: cross-section from a radius parameter / anthropometric ratio, independent of long-axis length. | SR |
| D7 | `sternoclavicular` is produced by the RTMPose mapping only. RTMPose and MediaPipe now emit different canonical landmark sets — the exact thing the tracker→canonical boundary exists to prevent. | Add the same `anatomical_offset` entry to `mediapipe_body_to_canonical_mapping.yaml`; spec in [`13`](../13-tracker-to-canonical-mapping.md) that **every tracker mapping must produce the full canonical landmark set**, and that a missing landmark is an error, not an omission. | SR → CODE |
| D8 | `sternoclavicular` is produced and consumed by nothing — absent from `canonical_body.yaml`, from the segment definitions, and from the schema. The clavicle still roots at the shoulder keypoint, the error [`12`](../12-standard-human-model.md) says `anatomical_offset` exists to fix. | Add it to the canonical landmark set and root the clavicle segment on it. §2 task 4 (landmark→segment attachment) is where the wiring is declared. | SR → CODE |
| D9 | The `anterior = up × lateral` sign in `anatomical_offset` was unverified pending the forward-axis. | **✅ Not a defect — verified correct.** The construction is **subject-relative** (`up` from hips→neck, `lateral` from left→right shoulder), so it holds regardless of which world-definition method the calibration used. Checked numerically at five arbitrary subject facings (0°/37°/90°/180°/265°): `up × lateral` reproduced true anterior exactly in every case. **It holds because the basis is right-handed** — the handedness guarantee is load-bearing for anatomy, not just rendering. Recorded in [`07`](../07-coordinate-conventions.md#subject-relative-constructions); the assertion still goes into doc 14's tests. | SR ✅ |

### 10b. Structure, hygiene, and contradictions

| # | Defect | Fix | Pass |
|---|---|---|---|
| D10 | `ChannelKind.ROTATIONS = 1` is commented "LEGACY … kept for backward-compat during transition", contradicting [`00`](../00-overview.md)'s "zero backwards-compatibility cruft" and locked decision 8. Only tests reference it. | **Delete the enum member.** Update the tests to use `ROTATIONS_WORLD`. Remove the specification of it from [`03`](03-canonical-frame-extensions.md). There is one version of the system. | SR → CODE |
| D11 | The canonical human is defined by `_get_standard_human()` **inside the freemocap aggregator** — inverting the boundary rule that SkellyForge owns the model. The `standard_human.yaml`-vs-Python `TBD` in [`standard-human-model/`](standard-human-model/README.md) was never closed, and the bootstrap filled the vacuum. | Close the TBD (§10c Q2). Spec the definition's home in SkellyForge, and spec its removal from the aggregator. | SR → CODE |
| D12 | `_BONE_TO_LANDMARK` and `HumanBone.proximal_landmark` hold the same fact in the same file; the bootstrap populates both and reads only the dict. | One source: the model's `proximal_landmark`. Delete the dict. Falls out of D11. | SR → CODE |
| D13 | `StandardHuman.get_children()` / `_get_bone_by_name()` are O(n) scans called per-segment inside the per-frame solve — ~O(n²), 2.07 ms/frame at 21 segments, ~14 ms extrapolated to 55. `bone_map` is rebuilt every frame. | Spec that the model builds name→segment and parent→children indices **once at load**, and that the solver takes the model as an already-indexed structure. | SR → CODE |
| D14 | `RotationsFrame` lookup in [`06`](06-rigid-body-bone-renderer.md) does `boneNames.indexOf()` per segment per frame — same O(n²) shape, in a plan otherwise careful about allocation. | §9 task 1: resolve to an index when the schema arrives. | SR |
| D15 | `setColorAt` is called every frame for colours that are static per instance. | §9 task 1: set once at schema time. | SR |
| D16 | Module-level mutable globals `_standard_human_cache` and `_prev_orientation_result` in the aggregator: never reset between sessions (stale damping carries across recordings) and shared if two pipelines run in one process. | Spec this state as owned by the pipeline/solver instance with an explicit reset on session start — not module scope. | SR → CODE |
| D17 | `_BONE_LENGTH_RATIOS` in `standard_human_model.py` is read by nothing. | Either it seeds the T-pose in D11's real definition, or it is deleted. Decide in D11; no dead table survives this pass. | SR → CODE |
| D18 | Local import inside `solve_bone_full_frame()`. | Move to module scope. | CODE |
| D19 | Dead cross-module import of the private `_check_strictly_increasing` carrying `# noqa: F401`. | Delete. | CODE |
| D20 | `Dict` / `List` / `Optional` survivals in `tracker_mapping.py` alongside 28 new-style annotations. | Convert to new-style. | CODE |
| D21 | `find_body_csv(path)` has an untyped parameter. | Annotate. | CODE |
| D22 | `StreamSchema` is specified `frozen=True` in [`03`](03-canonical-frame-extensions.md) and is mutable in code. | **Make it frozen** — a schema is an immutable declaration. Correct the code, not the spec. | SR → CODE |
| D23 | `lsl_bridge.py` docstring lists a "scalars" block kind that was dropped. | Correct the docstring. | CODE |
| D24 | `TrackerMapping.apply()` silently omits landmarks whose source keypoints are missing, while [`00`](../00-overview.md) states "Fail loudly, no fallbacks" as a blanket principle. | Silent-skip is **correct** for per-frame occlusion — a missing landmark this frame is data, not an error. But a mapping that references a keypoint the tracker never produces **is** an error and must raise at load. Spec both halves in [`13`](../13-tracker-to-canonical-mapping.md) and carve the occlusion exception into [`00`](../00-overview.md) so the principle stays true. | SR → CODE |
| D25 | Two workstream ID namespaces (`FMC-WS-n` and `SF-SH-n`/`ST-SH-n`) for overlapping work; FMC-WS-5 and `standard-human-model/` are two live plans for the same thing. | §4 tasks 4–6. | SR |
| D26 | [`06`](../06-backend-refactor-and-cleanup.md) cites three `core/kinematics/` paths that no longer exist; `HANDOFF` says the folder was "deleted" when it was **moved**; `HANDOFF` file map lists a retired file; `HANDOFF` "Uncommitted" list is wrong; "12 tests" is now 23; [`01`](01-standard-stream-contract.md) headers name files that were renamed; [`README`](../README.md) says nothing is implemented. | §8, all of it. | SR |
| D27 | [`09`](../09-standard-stream-protocol.md)'s open-questions bullet says subject count is "not in the schema", contradicting its own callout box and `max_persons` in code. | §2 task 5 — delete the stale bullet. | SR |
| D28 | `CoordinateConvention.rotation_frame` is a single value while both rotation frames ship — the field cannot tell the truth. | §2 task 6 — make it per-channel-group or drop it. | SR → CODE |
| D29 | `pubsub_topics.py` types the rotation dicts as `dict[TrackedPointNameString, …]`; the keys are segment names. | Introduce a `SegmentNameString` type alias and use it. | SR → CODE |
| D30 | `stream_schema.py` imports `StandardHuman` at module scope, coupling the wire contract to the model — FMC-WS-1 specified it as a standalone contract. | Decide: either the coupling is intended (and [`01`](01-standard-stream-contract.md) is corrected to say so) or `from_standard_human` moves to a boundary module. Not left ambiguous. | SR |
| D31 | SkellyForge has **no test infrastructure at all** — `pytest` collects nothing across ~3,200 lines of new math. | §5 — doc `14` specifies the suite and the `skellyforge/tests/` scaffold. | SR → CODE |
| D34 | `FREEMOCAP_CANONICAL_CONVENTION` in `coordinate_convention.py` sets `forward_axis=Axis.PLUS_Y` with a `# TODO(convention): confirm`. **The canonical standard is `+X` forward** — the value is simply wrong, and every adapter conversion derived from it would be rotated 90° about Z. | Set `forward_axis=Axis.PLUS_X`; delete the `TODO`. Per Q1. | SR → CODE |
| D36 | [`02`](02-backend-encoder-and-ws-reshape.md) § Transition strategy specifies a `FREEMOCAP_STANDARD_STREAM=1` feature flag and **dual-protocol coexistence** during the send-path swap — contradicting [`00`](../00-overview.md)'s "zero backwards-compatibility cruft" and locked decision 8 ("Replace, don't parallel"). Nothing has shipped this wire format, so there is no consumer to stay compatible with; the flag's only effect is keeping the legacy path alive. | **Delete the flag and the legacy path in one change.** The distinct first-byte tags (legacy 3/4/5 vs. standard stream 10/11/12) already prevent collision, and FMC-WS-4 lands the decoder in the same cycle. *(Judgment call rather than dead code — a flag during a risky send-path swap is defensible engineering; it loses to the stated rule, but say so if you want it kept.)* | SR → CODE |
| D35 | The canonical convention is a **standard the data must satisfy** (`+Z` up, `+X` forward). The charuco ground-plane path establishes it. The **camera-0-pinned** path (used when ground-plane alignment is skipped or fails — anipose logs a warning and continues) leaves the world in camera 0's optical frame, which is not Z-up. Data would then violate the invariant while the schema declares it holds. | Verify what the camera-0 path actually produces. Either it re-orients into the canonical convention before data flows, or the gap is closed explicitly. **Not** a reason to weaken the schema — the standard stands; a path that doesn't meet it is the defect. | SR → CODE |
| D33 | [`01`](../01-canonical-data-model.md) stated the rest-pose contract as *"a bone reading `(0,0,0,1)` is in the rest pose"* — that is **xyzw**. This codebase's canonical order is **wxyz**, where identity is `(1,0,0,0)`. The doc asserting the identity convention had it backwards, inside the section warning about horrifying-pose bugs. | **Fixed in the §1 sweep.** Corrected to `(1, 0, 0, 0)` with the order named explicitly. Every doc that prints a literal quaternion must name its component order — added to §5's test spec as an assertion. | SR ✅ |
| D32 | The `standard-human-model` sub-plan is marked **DONE** while four of its own definition-of-done bullets are unmet (mediapipe landmarks, `bs/`-parity tests, posthoc `Human` rebuild, face channels present-and-null). | Correct the status to reflect what is actually done, and move the unmet bullets into explicit open tasks. Status ambiguity is the failure [`HANDOFF_GUIDE`](../HANDOFF_GUIDE.md) exists to prevent. | SR |

### 10c. Open questions — all answered

Nothing carried forward as "open". Each is resolved here or has a named closing action in this pass.

| # | Question | Answer |
|---|---|---|
| Q1 | Canonical **forward-axis** — `TBD` in the code and docs. | **✅ Resolved 2026-08-12: `+X`.** The FreeMoCap canonical convention is `mm · right-handed · +Z up · +X forward` (robotics/biomechanics standards). It is a **declared internal standard**, not something derived from whatever the calibration produced — all FreeMoCap data is in it internally, conversion happens at the adapter edge on request, and re-orientation is an explicit user action through the HTTP control plane. The `TBD` was never a research question; it was an undeclared standard. Stated in [`07`](../07-coordinate-conventions.md#the-freemocap-canonical-convention). |
| Q2 | Where the canonical segment definition lives — `standard_human.yaml` or Python. | **Close it in this pass** as part of D11, and record the choice in [`standard-human-model/`](standard-human-model/README.md) with its rationale. |
| Q3 | Does `ROTATIONS_WORLD` have a consumer? | **Resolved: yes, and it stays.** The stream carries everything (§2); it is small data, and [`06`](06-rigid-body-bone-renderer.md) drives the viewport from it directly. |
| Q4 | Where reprojection gets camera parameters. | **Resolved (§3):** the existing camera calibration infrastructure. If we reconstruct 3D, we know the cameras. |
| Q5 | `q_world` direction — segment-frame→world, or the inverse? | **✅ Resolved 2026-08-12: segment-frame → world.** `q_world` carries a segment from its declared rest orientation to its current one — which *is* the `identity == T-pose` contract, so no other reading is consistent with the rest of the spec. The composition `q_local = conj(q_parent) · q_child` follows. Stated in [`07` § Segment rotation conventions](../07-coordinate-conventions.md#segment-rotation-conventions); still to be confirmed empirically by doc 14's round-trip test before D1's fix lands. |
| Q6 | Where engine-testing strategy lives. | **Resolved:** new doc `14` (§5), sibling to `08`. |
| Q7 | Critical damping vs. first-order lag. | **Resolved:** real critical damping (§6, D4). |
| Q8 | What the channel groups enumerate. | **Resolved:** six groups, everything on the wire (§2). |

---

## Order of execution

1. **§1 terminology** — everything else is written in this vocabulary, so it goes first.
2. **§10c Q1 forward-axis** — read the ground-plane calibration basis and state the axis. Small, and D9's
   offset sign plus the whole coordinate converter hang off it.
3. **§2 channel groups** + **§3 overlay layers** — the wire contract, now expressible.
4. **§7 quaternion convention** + **§10c Q2 definition home** — both close open `TBD`s that later sections
   are written against.
5. **§5 doc 14** + **§6 damping spec** — what the code pass implements against.
6. **§4 sequencing** + **§8 stale sweep** + **§9 FMC-RB fixes** + the remaining **§10** SR-pass rows.

Then the **code pass**, in this order: stand up `skellyforge/tests/` and write the engine suite (it confirms
Q5 empirically) → D1 → D3/D4 critical damping → D7/D8 sternoclavicular → D10–D31 → FMC-WS-2.

## Definition of done

- The keypoint / landmark / segment distinction is stated in exactly one place and every doc uses it.
- [`09`](../09-standard-stream-protocol.md) is the sole authority on channel content; `phase-1/03` defers
  to it.
- Both overlay layers are specified, sourcing camera parameters from the existing calibration
  infrastructure.
- `14-engine-testing-strategy.md` exists and is cross-linked.
- Critical damping is specified precisely enough to implement without further decisions.
- The world-quaternion convention and the canonical forward-axis are both written down; no `TBD` remains in
  [`07`](../07-coordinate-conventions.md) or `coordinate_convention.py`.
- No doc asserts a superseded sequencing decision; FMC-WS-5 no longer exists as a parallel plan.
- **Every row in the §10 defect register is either fixed (SR) or has its target written down (CODE).
  Nothing is deferred, nothing is marked acceptable, and §10c contains no unanswered question.**
- [`IMPLEMENTATION_PLAN`](../IMPLEMENTATION_PLAN.md) § Dependencies & blockers carries no entry that this
  pass was supposed to resolve.
