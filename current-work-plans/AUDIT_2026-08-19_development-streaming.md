# Audit — `development-streaming` across skellyforge / skellytracker / freemocap

**Date:** 2026-08-19
**Commits audited (all three local HEADs == `origin/development-streaming`, verified byte-identical):**

| repo | HEAD | subject |
|---|---|---|
| freemocap | `26edfbdd` | `hands??` |
| skellyforge | `0f88476` | `hands??` |
| skellytracker | `5f1010f` | `wee` |

skellycam is on `development-streaming` too but is 4 files / 16 lines off its own `development` — effectively untouched by this effort. Not audited in depth.

**Nothing on your machine was modified.** All experiments ran on fresh clones in my sandbox.

---

## 0. Method, and what "verified" means here

Every claim below is one of:

- **[MEASURED]** — I ran the real code and have numbers.
- **[READ]** — I read the source and am reporting what it says.
- **[QUESTION]** — I don't know your intent; see §8.

I built the actual `SkeletonDefinition`, built the actual T-pose, ran the actual
`rigidify_landmarks` and `solve_frame_orientations`, and ran the test suites.
The load is green: **95 segments / 94 linkages / 25 chains / 146 landmarks**, one
root (`pelvis`) — exactly what the docs claim.

**Caveat:** your working tree has uncommitted WIP — 8 modified files plus 3
untracked (`PickingRegistry.ts`, `ViewportPicker.tsx`, `ViewportInspection.tsx`)
in `freemocap-ui/src/components/viewport3d/`. That's a hover/click inspection
feature, unrelated to the bone math. My audit covers committed HEAD only.

---

## 1. The ontology, as I read it — correct me if this is wrong

I want to state this back explicitly, because if I have it wrong every judgement
below is wrong.

**Seven layers, each an object with a static (authored) face and a hydrated
(per-frame) face, each owning its own math:**

1. **keypoint** — a measured 3D world point, tracker-named. Pure measurement.
   Never derived, never added to. **Owner: skellytracker.**
2. **mapping** — *the one seam.* The rule that hydrates a landmark *from*
   keypoints (direct / mean / weighted / `anatomical_offset`). It converts
   measurement into an observation of a model point. It does **not** define
   landmarks. **Owner: the skellytracker↔skellyforge interface** (YAMLs ship in
   skellytracker; `.apply()` is called in freemocap so skellyforge never imports
   skellytracker).
3. **landmark** (`AnatomicalLandmark`) — a named point **defined in the local
   frame of a segment**. Static: name + anatomical definition + `local_position` +
   `segment` (explicit ownership). Hydrated: a world position per frame —
   i.e. a trajectory. **Owner: skellyforge.**
4. **segment** (`RigidBodySegment`) — a **rigid body**: origin + orientation +
   length, solved from its landmarks. Fully specified at 3+ non-collinear
   landmarks (Kabsch); partially specified at 2 (swing + damped minimal roll).
   `length` is **derived** from `local_position`, never authored as a ratio.
5. **linkage** (`JointLinkage`) — **two segments that share a point**. Derived
   from parent edges; the child's `origin_landmark` *is* the shared point. Math:
   `q_local = conj(q_parent) · q_child`.
6. **chain** (`KinematicChain`) — **3+ linked segments**, a `start`→`end` path in
   the tree. Straight (a limb) or branching (the wrist fan). The IK/FABRIK unit.
7. **skeleton** (`SkeletonDefinition`) — a collection of chains composing one standard
   human.

**Responsibility split:**
`skellytracker (keypoints) → [mapping: the one seam] → skellyforge (landmark→segment→linkage→chain→skeleton) → freemocap (pipelines + adapters)`.
freemocap has two consumers of one model: realtime (online, damped) and posthoc
(batch). skellyforge never imports skellytracker or freemocap.

**Conventions:** mm · right-handed · **+Z up** · **+X forward** · **+Y = subject's
left**. Quaternions **wxyz**. **`identity == T-pose`, world and local.**
`q_child_local = conj(q_parent) · q_child_world`. Body/hand segments declare
their primary direction on **`y`**, +Y toward the child (VRM 1.0); face bones on
**`z`**. Mirroring negates **Y only** and rebuilds the frame right-handed.

If any of that is wrong, stop and tell me before reading further.

---

## 2. THE HEADLINE: one line of code is corrupting the entire skeleton, every frame

### 2.1 The evidence [MEASURED]

I fed the pipeline **the model's own T-pose landmarks** — the exact reference
geometry, restricted to the subset a tracker mapping can actually hydrate — and
ran the aggregator's exact order (`map → estimate → build_tpose → rigidify →
solve`). Under `identity == T-pose`, every solved quaternion must be identity and
every landmark must land on its own rest position.

| configuration | segments solved | >1° off identity | max angle error | max landmark error |
|---|---|---|---|---|
| **as committed** | 89/95 | **77** | **178.8°** | **146.9 mm** |
| complete + perfect landmarks, no rigidify | 95/95 | 0 | 0.0° | — |
| complete + perfect landmarks, with rigidify | 95/95 | 0 | 0.0° | 0.0 mm |
| sparse (tracker-producible), no rigidify | 46/95 | 0 | 0.0° | — |

Read that table carefully. **The solver, the T-pose builder, and the quaternion
math are all correct.** They reproduce identity exactly. The corruption enters at
exactly one stage: `rigidify_landmarks` operating on *sparse* input — i.e. the
normal case, on every frame.

`right_hand` comes out **178.8° off**. `trunk_center` is displaced **147 mm**,
`head_vertex` 140 mm, both sternoclaviculars ~137 mm. This is not a hand problem.
**It is a whole-skeleton problem that is most visible in the hands.**

### 2.2 The mechanism [READ + MEASURED]

`skellyforge/kinematics/skeleton_rigidifier.py:25`

```python
# Direction used for a bone that has never been observed.
_FALLBACK_DIRECTION: np.ndarray = np.array([0.0, 1.0, 0.0])
```

`TreeRigidifier.rigidify` walks the parent-edge tree and, for each child whose
origin landmark is missing this frame, places it at
`parent_position + direction * length`, where `direction` falls back to
`_FALLBACK_DIRECTION` — **world +Y, the subject's left**.

**49 of the 94 non-root segment origins are landmarks that NO tracker mapping can
ever produce.** [MEASURED] They aren't occluded — they are structurally
unobservable (`hand_trapezoid`, `hand_capitate`, `hand_hamate`, all seven
tarsal/cuneiform bones, every toe joint, and `lumbosacral_junction`). So this
isn't a rare occlusion fallback. **It fires 49 times per frame, always.**

Then everything downstream eats the fabrication:

- `left_index_finger_metacarpal.origin` = `left_hand_trapezoid` → fabricated at
  wrist + [0,1,0]·26.5 mm. Every finger's MCP joint is then placed *relative to*
  that fabricated carpal, so the observed MCP keypoints get dragged off.
- The `hand` segment has 14 landmarks, so it takes the **Kabsch** path — fitting
  its rest cloud against a live cloud that now contains 3+ fabricated points all
  lying on a single ray out of the wrist. Hence 178.8°.
- `spine.origin` = `lumbosacral_junction` → fabricated sideways → **the entire
  axial chain (spine → chest → neck → head) hangs off a point placed to the
  subject's left instead of above the pelvis.** That's the 137–147 mm on the head
  and sternoclaviculars.

### 2.3 The one-line proof [MEASURED]

I replaced only the fallback — per-segment T-pose rest direction
(`normalize(child_origin_rest − parent_origin_rest)`) instead of the hardcoded
`[0,1,0]` — changing nothing else:

```
BASELINE (as committed):   89/95 solved | 77 non-identity | max 178.8° | max 146.9 mm
FIX B only (fallback):     89/95 solved |  0 non-identity | max   0.0° | max   0.0 mm
```

**One change. Whole skeleton exact.**

For comparison, fixing `hand.yaml`'s rest directions (§2.5) *alone* barely moves
it (77 → 66 non-identity). **I initially expected the hand YAML to be the primary
cause. The experiment says it is not.** Fix the fallback first.

### 2.4 Why the mitigation that was supposed to prevent this is dead [READ]

`TreeRigidifier`'s docstring:

> Per-bone last-good directions are carried across frames so a joint that drops
> out for a few frames is gap-filled along its last direction instead of
> collapsing onto its parent.

`skeleton_rigidifier.py:202` — the **only** production construction site:

```python
corrected_origins = TreeRigidifier(joint_hierarchy).rigidify(origins, bone_lengths)
```

A **stateful** class is constructed **fresh on every frame**. `_last_direction`
is empty at the start of every call. The cross-frame memory has never once
worked in production.

Worse: `freemocap/tests/rigid_body/test_tree_rigidifier.py::test_missing_child_gapfilled_from_last_direction`
**passes** — it exercises the class in isolation across two calls on one
instance. Green unit test, dead integration. This is the exact shape of bug that
CI would have caught if CI ran (§6).

This is item **#4 on your "Next work" list** — "Unhydrated-segment fallback ... so
a hidden hand doesn't stick out sideways." **The plan mis-scopes it as cosmetic.
It is the single load-bearing defect on this branch.**

### 2.5 The second hand bug: `hand.yaml`'s rest directions are copy-pasted from `foot.yaml` [MEASURED]

Every hand segment in `skellyforge/.../definitions/hand.yaml` carries
`rest_direction: [1, 0, 0]` — world **+X, anterior**. That is correct for a foot
(toes point forward). It is wrong for a hand, which must continue the arm along
**±Y**.

Two consequences:

1. **At T-pose, both hands stick straight out the front of the body**, 90° to the
   arms. [MEASURED] Left wrist `[0, 775, 525]` → left middle-finger tip
   `[200, 775, 525]`. Y unchanged; 200 mm of +X.
2. **The right hand is not mirrored.** Mirroring negates Y only, and `[1,0,0]`
   has no Y. Right middle-finger tip is also `[200, −775, 525]`. **Both hands
   have identical rest geometry.** The "left == right local geometry, only
   `rest_direction` mirrors Y" rule silently produces no mirror at all here.

Feeding a *physically real* T-pose (hands continuing the arms) into the committed
model, with the §2.3 fallback fix applied so it isn't a confound: [MEASURED]

```
left_lower_arm        world   0.00°     (correct)
left_hand             world  98.23°     LOCAL (== wrist joint angle)  98.23°
right_hand            world  98.23°     LOCAL (== wrist joint angle)  98.23°
left_foot             world   0.00°     LOCAL   0.00°   (foot.yaml is right)
```

**Both wrists report a 98.23° joint angle when a person is standing in a T-pose,
and both report the same sign.** `identity == T-pose` — described in
`conventions.md` as "the contract every downstream consumer relies on" — is
broken for all 40 hand segments. Any VRM/VMC retarget, any joint-angle
biomechanics, any `conj(q_parent)·q_child` consumer inherits a 98° wrist offset.

A candidate fix I verified reproduces a correct T-pose (left tip `[0,975,525]`,
right tip `[0,−975,525]`, properly mirrored):
- every hand segment's primary axis → `rest_direction: [0, 1, 0]` (mirrors to `[0,-1,0]`);
- the `hand` segment's twist axis (`x` → `hand_hamate`) → `rest_direction: [-1, 0, 0]`
  (ulnar side is posterior with the palm down; unchanged by Y-mirror, which is
  correct for both hands).

I have **not** applied this to your repo. See §8 — I want your read on the
palm-down vs palm-forward T-pose convention before touching authored anatomy.

### 2.6 Three carpals/tarsals are unobservable *by construction*, not by occlusion [READ]

Even with the fallback fixed, the hand's internal pose is a rigid extrapolation,
not a measurement. Both hand mappings hydrate `hand_trapezium` (thumb CMC) and
the five MCP joints, and explicitly document that the other seven carpals "ride
the hand rigid solve." But **`hand_trapezoid`, `hand_capitate`, and `hand_hamate`
are the declared `origin_landmark`s of the index / middle / ring+pinky
metacarpals.** So the metacarpal linkages are anchored on points nothing measures.

That's a legitimate design choice under "observation-first, IK where not
measured" — but right now there is no IK, so those origins come from whatever the
rigidifier's fallback happens to produce. **[QUESTION §8.2]**

---

## 3. Other correctness / math findings

### 3.1 `align_point_sets_kabsch` never detects degeneracy, despite its docstring [MEASURED]

`coordinate_frame_ops.py:382`. Docstring:

> Raises ValueError ... if the points are collinear / degenerate.

It does not. The only guard is `det(R) ≈ 1` after Umeyama correction — and a
collinear point set yields a perfectly valid `det = +1` rotation that is
**unconstrained about the line**. Demonstrated:

```
collinear triple, live rotated 37° about the free axis  →  R = that 37° rotation, no exception
collinear triple + 0.5 mm noise                          →  R returned, no exception
```

**Where this bites:** the `pelvis` — the root of the whole skeleton — has 7
landmarks but only 3 are tracker-hydrated: `hips_center`, `left_hip`,
`right_hip`. And `hips_center` is the *mean* of the other two. **The root
segment's Kabsch fit runs on three exactly-collinear points every frame.** Pelvic
roll/tilt is mathematically unrecoverable from that; the SVD silently returns
whatever least-squares gives. The rest of the body hangs off it.

`orientation_solver.py:135` then does `except ValueError: pass`, and
`rigid_point_set.py:325` does `except ValueError: return observed` — so even if
the check existed, both call sites swallow it. Three separate violations of
fail-loud in the hot math path.

### 3.2 Four linkages share a name — the "global unique IDs" invariant is broken [MEASURED]

```
left_hand_hamate, right_hand_hamate, left_foot_cuboid, right_foot_cuboid
```

`ring_finger_metacarpal` and `pinky_finger_metacarpal` both declare
`origin_landmark: hand_hamate`; `fourth_metatarsal` and `fifth_metatarsal` both
declare `origin_landmark: foot_cuboid`. `derive_linkages` names a linkage after
its shared landmark, so you get duplicates. Anatomically defensible (both
metacarpals do articulate with the hamate) but it violates the constitution's
first invariant and makes `linkages` unindexable by name.

It also makes `rigidify_landmarks` write the same landmark twice per frame from
two different tree nodes (harmless today — both compute the same value — but it's
a silent last-writer-wins).

### 3.3 `left_hand` and `right_hand` belong to no chain [MEASURED]

25 chains cover **93 of 95** segments. The two missing are `left_hand` and
`right_hand`.

`arm: {start: clavicle, end: lower_arm}` stops at the forearm; the five finger
chains start at the metacarpals. The carpus falls between them. Compare the leg:
`leg: {start: pelvis, end: foot}` **does** include the foot.

`segment-model.md` says "the five chains share the `hand` segment (the carpus) as
their common ancestor — exactly the branching structure FABRIK reconciles." The
model as built does not express that: nothing reaches the hand through the chain
layer, so any future FABRIK pass will skip it. Arm/leg asymmetry, unnoticed.

### 3.4 `_mean_position` silently returns a partial mean [READ]

`skellytracker/core/io/tracker_mapping.py:559`. Docstring: "or None if any
missing." Code: returns `None` only if **all** are missing.

So `hips_center: ["left_hip", "right_hip"]` with only the left hip visible
returns **the left hip's position, labelled `hips_center`** — an 88 mm lie with no
signal. Same shape in `apply()`'s list form (line 265) and the weighted-dict form
(line 279, which renormalizes by the surviving weights). For a root segment whose
Kabsch is already degenerate (§3.1), this is a bad combination.

### 3.5 The rigidifier's tree pass and its Procrustes pass fight each other [READ]

`rigidify_landmarks` first runs the forward tree pass (writing every segment
origin), then loops over every 3+-landmark segment running a rotation-pinned
Procrustes that **overwrites those same origins**. Last writer wins, and the
order is `skeleton.segments` order. `upper_leg` and `lower_leg` share `knee`;
`lower_leg` runs later and overwrites it. Two competing corrections applied
sequentially, with no statement anywhere of which is authoritative.

### 3.6 `build_standard_human_tpose` assumes an unvalidated invariant [READ]

`tpose.py:133` computes a child's world origin as
`parent_basis.T @ origin_landmark.rest_position` — i.e. it interprets the origin
landmark's rest position in the **parent's** frame. The landmark loop 15 lines
below correctly uses `geometries[lm.reference_frame]`.

Today the assumption holds for all 94 non-root segments [MEASURED, 0 violations].
But nothing enforces it. Author one segment whose `origin_landmark.reference_frame`
isn't its parent and the T-pose silently deforms. Same class of gap for
`RigidBodySegment.length`, which assumes the primary target's `segment`
is the segment itself (also 0 violations today, also unchecked).

### 3.7 Nothing checks that a segment's `rest_direction` agrees with its parent [READ]

This is the structural hole that let §2.5 in. `_build_rest_basis` builds each
segment's rest frame **purely from its own authored `rest_direction`s**, ignoring
where the parent chain actually places it. So a child can declare a rest
direction 90° off its parent's and the loader, the validators, and every test
will pass. There is no assertion anywhere that the assembled T-pose is
anatomically continuous.

### 3.8 Quaternion math: clean [MEASURED]

I hammered `rotation_quaternion.py` with 2000 random rotations each:

```
from_rotation_matrix ∘ to_rotation_matrix   max error 1.3e-15
(a*b).rotate(v) == a.rotate(b.rotate(v))    0 failures / 2000
conj(q).rotate(q.rotate(v)) == v            0 failures / 2000
+90° about z → (0.7071, 0, 0, 0.7071); rotate([1,0,0]) → [0,1,0]   correct
```

`align_point_sets_kabsch`'s Kabsch/Umeyama is textbook-correct.
`compute_rotation_from_live_basis`'s `R = live.T @ ref` is correct.
The frontend's `world = R_world · R_rest · Q · S` composition in
`RigidBodyBoneInstances.ts` is correct, and its `rest_orientation` (=
`basis.T`, local→world) matches the backend. **The rendering pipeline is not the
problem.** It is faithfully rendering bad geometry.

### 3.9 The aggregator's "quaternions never depend on lengths" comment is false [MEASURED]

`realtime_aggregator_node.py:339`. True for 2-landmark segments. False for 3+:
`build_standard_human_tpose` scales each landmark by
`scales[lm.reference_frame]`, and a 3+-landmark segment's cloud mixes reference
frames — so the cloud is **non-uniformly** deformed and the Kabsch rotation
shifts. Magnitude is small (0.295° on `left_hand` for a 30 % metacarpal / 15 %
carpus length change), so this is a docs-correctness issue, not a live defect.

---

## 4. Drift: where the plans and the code disagree

The docs' own house rule is "reconcile, don't defer." Here's the ledger. The
plans are dated **2026-08-18**; there are ~8 commits after that (`lenths`,
`names`, `hands n feet`, `hands?`, `hands??`, `wee`) that the docs never absorbed.

| # | The plan says | The code says |
|---|---|---|
| D1 | `IMPLEMENTATION_PLAN.md:33` — solve port "DONE (identity-at-T-pose green)" | The identity test **cannot run**: 14/15 tests in `test_solver_keypoint_declared.py` fail with `TypeError: solve_frame_orientations() missing 1 required keyword-only argument: 'state'`. Never updated for the `(result, state)` split. The end-to-end contract is **77/89 segments wrong** (§2.1). |
| D2 | `README.md:55` / `realtime-loop.md:32` — "Closed end to end … the live loop runs + overlays match" | The loop runs. Every solved orientation downstream of an unobservable origin is wrong. "Runs" ≠ "correct." |
| D3 | Next work #4 — unhydrated fallback, so "a hidden hand doesn't stick out sideways" | It is not a hidden-hand edge case. It fires 49×/frame on normal input and corrupts head, torso, hands and feet (§2.2). Scope is wrong by an order of magnitude. |
| D4 | Progress log — "Lazy heavy-dependency imports — mediapipe **+ onnxruntime** … DONE" | mediapipe: done (3 function-scope imports). **onnxruntime: still module-scope** in `onnx_session.py:35` and `ort_session_utils.py:18-19`; `onnx` module-scope in `_yolox_dynamic_batch.py:36`. |
| D5 | `mapping_paths.py` — "IMPORT-LIGHT BY DESIGN … Only pathlib"; `tracker_mappings.py` — "must NOT drag the … trees in at startup" | Importing `skellytracker.core.io.mapping_paths` pulls **847 modules** including `cv2` and `tqdm` [MEASURED], because `skellytracker/core/__init__.py` eagerly imports `core.io` → `process_video`. onnxruntime/mediapipe do stay out; the stated guarantee is otherwise unenforced. |
| D6 | CLAUDE.md — "skellyforge **never imports** skellytracker … `tracker_contract.py` was deleted together with that contract" | `skellyforge/pyproject.toml` still declares **`skellytracker` as a runtime dependency**, with a comment justifying it by the load-time mapping contract *that no longer exists*. The only remaining import is `tests/test_face_mapping_consistency.py:30`. Stale dependency + stale justification + reintroduced boundary crossing. |
| D7 | HANDOFF #5 — "No `upper_chest`"; #6 — eyes/ears/nose are landmarks, not segments | `center_of_mass.py`'s module docstring still maps de Leva onto `upper_chest`, `shoulder`, `eyes`, `jaw`, "the four finger segments", `toes` — all retired names. `standard_human/__init__.py:3` still says "the composed **60-segment** human" (it's 95) and its `__all__` exports **only** old-architecture symbols — `SkeletonDefinition`, `AnatomicalLandmark`, `RigidBodySegment`, `JointLinkage`, `KinematicChain` are not exported from their own package. |
| D8 | Ontology decision #2 — "Primary/twist, not exact/approximate. **No `kind` field.**" | skellytracker's `anatomical_offset` frames still use `kind: exact \| approximate` (and hard-require exactly one of each). `coordinate_frame_ops.build_segment_frame` still dispatches on `AxisKind.EXACT/APPROXIMATE` imported from the retired `segment_definition.py` — it would `AttributeError` on a new `AxisDefinition`. **[QUESTION §8.1]** |
| D9 | Realtime loop docstring — "Only real (non-extrapolated) keypoints teach lengths" | `measured_keypoints` is built at `realtime_aggregator_node.py:664` and **never read**. `estimate_segment_lengths` is fed `mapped_landmarks`, derived from `filtered_keypoints`, which **includes** the Euro filter's gap-filled predictions. The stated invariant is not implemented. |
| D10 | `mapping's output is a landmark` (tracker-mapping.md) | Both body mappings emit **6 names the skeleton does not declare**: `jaw`, `mid_sternum`, `left_mouth`, `right_mouth`, `left_foot_ball`, `right_foot_ball`. Computed every frame, discarded. Their comments reference "Task 3"/"Task 4" and "the jaw segment's rest direction" — a jaw segment that no longer exists. |
| D11 | `HumanSkeleton.required_landmarks()` — "the anchor landmarks the solve MUST hydrate from the tracker mapping" | 117 required; the mediapipe and rtmpose mappings each miss **53 of them** [MEASURED]. The method has **zero production call sites** — it's the natural place to enforce the seam and nothing calls it. |
| D12 | Conventions — mm, **+Z up**, +X forward | `freemocap/tests/test_full_loop.py:_standing_pose` is authored **"+Y-up"** with left = −X. The one end-to-end gate test runs the pipeline in a 90°-rotated world, and its docstring pre-excuses itself by deferring the identity contract to "skellyforge's own tests" — which don't run (D1). **The identity-at-T-pose contract is asserted nowhere that executes.** |
| D13 | `foot.yaml` bone lengths | first metatarsal 18 mm (real ≈ 65), second 20 mm (≈ 75), big-toe proximal phalanx 15 mm (≈ 30). Roughly ⅓ scale. Hand lengths are broadly plausible; the foot is not. **[QUESTION §8.3]** |

Also stale, minor: `_reproject_segment_origins`'s docstring says "(60, 3)" and
"(n_cameras, 60, 2)" — it's 95. `CoordinateConvention.rotation_frame` defaults to
`LOCAL` while the renderer consumes `ROTATIONS_WORLD`.

---

## 5. Anti-patterns

**Fail-loud violations in the hot math path** (against your stated preference and
skellyforge's own CLAUDE.md):

- `orientation_solver.py:135` — `except ValueError: pass  # degenerate this frame`
- `orientation_solver.py:183` — `except ValueError: pass  # collinear`
- `rigid_point_set.py:325` — `except ValueError: return observed` unchanged
- `orientation_solver.py` lines 111, 116, 141, 145, 152 — five bare `continue`s
  that silently drop a segment from the frame with no record of which or why
- `orientation_solver.py:213` — if a parent failed to solve, the child's **local
  quaternion is silently set to its world quaternion**. That is a math error
  wearing a fallback's clothes: the renderer then applies a world rotation as a
  local one.
- `tracker_mapping.py:559` — partial mean labelled as a full mean (§3.4)

**Stateful objects rebuilt per frame** (the design in the docstring is not the
design in the wiring):

- `TreeRigidifier(joint_hierarchy)` — per frame; kills the last-good-direction
  memory (§2.4)
- `RigidPointTemplate(...)` — rebuilt per frame per 3+-landmark segment, with
  defensive array copies and a fresh index dict, despite `rigid_point_set.py`'s
  own docstring: "build an invariant template **once** … then, per frame, find the
  best rigid placement"
- `_pairwise_distances(names, rest)` — computed every frame for every 3+-landmark
  segment (~390 norms/frame) and **never read**: `fit_template_to_observed` only
  touches `positions`. `pair_distances` is consumed solely by `from_distances`,
  which the live path never calls.
- `skeleton_rigidifier.py:206` — `next(s for s in skeleton.segments if s.name == name)`
  inside the per-origin loop: an O(95) scan × ~95 origins ≈ 9 000 comparisons/frame
- `segment_length_estimation.py:82` — the rolling window is a **tuple rebuilt by
  concatenation** every frame for all 95 segments (~7 000 element copies/frame at
  30 fps × 2.5 s)

**Dead / duplicated:**

- `coordinate_frame_ops.build_segment_frame` — stale against the new
  `AxisDefinition` (no `.kind`); its module docstring still describes the retired
  `SegmentReferenceGeometry`
- `coordinate_frame_ops.py:508-542` — 35 lines of thinking-out-loud comment
  ("Or …? Wait, let me be more careful.") left in production. Reads as a record of
  how the code got here, which is exactly what you've said comments must never be.
- `realtime_aggregator_node.py:813-821` — commented-out centroidal-kinematics
  block; `StreamingKinematics()` is constructed and `.reset()` is called but
  `.update()` never is, so `body_kinematics` is always `None` on the wire
- `AggregationNodeOutputMessage.skeleton` and `.standard_skeleton` are set to the
  same object
- **Three parallel segment-length systems live simultaneously:** the new
  `segment_length_estimation.py`; the old `kinematics/segment_lengths.py` (still
  exported from `kinematics/__init__.py`, still read by
  `freemocap/core/tasks/mocap/segment_length_io.py`, still reading
  `tracker_info/canonical_body.yaml`, still using retired names like
  `left_forearm`/`left_shank`, still carrying two `TODO (SF-SH-5)`s); and the
  derived `RigidBodySegment.length`.
- `standard_human/__init__.py` **eagerly imports the whole old architecture** —
  so `body_part`, `hand_part`, `face_part`, `standard_human_model`,
  `segment_parts`, `segment_definition`, `reference_geometry`,
  `human_bone_aliases`, `human_blendshapes` all load on every `SkeletonDefinition`
  import. The old system is not dormant; it's resident.
- The mapping — **the one seam of the ontology** — is applied by
  `BodyBiomechanics.apply_tracker_mapping` in a module named `center_of_mass.py`.
  The ontology's central interface is a method on a center-of-mass loader.

**Latent, not yet firing:** `_compose_parts` (`human_skeleton.py:130-149`)
handles collisions asymmetrically — a non-sided part `.update()`s (overwrites),
a sided part only writes `if new_name not in landmarks` (first-wins). Both are
silent and both depend on YAML key order. No collisions exist today [MEASURED],
so this is a trap, not a bug.

---

## 6. Process: this branch has had no CI at all

| repo | test workflow | triggers on |
|---|---|---|
| skellyforge | **none exists** — only `bump_version` and `publish_to_pypi` | — |
| skellytracker | `tests-fast` / `tests-full` / `lint` | `branches: [main]` |
| freemocap | `test.yml` | `branches: [main, development]` |

**Nothing has run on `development-streaming`, in any repo, for the entire
lifetime of this branch.** That is the root cause of §4 as a category.

Suite status as of HEAD:

- **skellyforge: 123 passed, 16 failed.**
  - `test_solver_keypoint_declared.py` — **14 failures**, all `TypeError: …
    missing 1 required keyword-only argument: 'state'`. This file contains
    `test_identity_at_t_pose`, `test_every_segment_produces_an_orientation`,
    `test_composition_round_trip_recomposes_parent_and_local`,
    `test_damping_continuity_across_frames`. **The entire orientation-solver test
    suite is dead against a superseded API.**
  - `test_lower_body_skeleton.py` — 2 failures: asserts 7 segments (now 45) and
    21 foot landmarks (now 13). Never updated when `foot.yaml` was re-authored.
  - 6 of 11 test files still import old-architecture symbols
    (`StandardHuman`, `SegmentDefinition`, `SegmentPart`, `ReferenceGeometry`).
- **skellytracker: 140 passed**, 42 collection errors — all missing optional
  extras (mediapipe / onnx), environmental. The two new files
  (`test_mapping_paths.py`, `test_mouth_mapping.py`) pass.
  Note: `test_mapping_completeness.py` + `fixtures/standard_human_required_keypoints.txt`
  were **deleted** on this branch alongside `tracker_contract.py`. Consistent with
  decision #4, but it removed the only check that the mapping's outputs are names
  the skeleton declares — which is why D10's 6 orphans survive.
- **freemocap:** not runnable in my sandbox (needs skellycam + the full env).
  Reviewed by reading.

**The two test files that would have caught the two headline defects are exactly
the two that are broken.** And `test_full_loop.py` — the designated end-to-end
gate — runs in the wrong coordinate convention and explicitly defers the identity
contract to the suite that doesn't run.

---

## 7. Performance [MEASURED]

Per frame, single core in my container (treat as an order-of-magnitude signal,
not your hardware):

```
estimate_segment_lengths      1.4 ms
build_standard_human_tpose    5.2 ms   (full 95-segment tree walk + 146 landmarks, per frame)
rigidify_landmarks            3.6 ms
solve_frame_orientations     21.6 ms
─────────────────────────    34.6 ms   ≈ 29 fps ceiling for reconstruction alone
```

That's before triangulation, Euro filtering, the velocity gate, center of mass,
reprojection into every camera, and CBOR assembly — all in the same Python
process. Profile of the solve: **328 `np.cross` calls/frame** (each dragging
`moveaxis` + `normalize_axis_tuple`), and **164 `_check_unit_vector` calls/frame**,
each doing `np.isclose` — a defensive assertion costing ~18 % of the solve. All of
it is 3-element vector work routed through numpy's generic dispatch.

---

## 8. Questions — answered by jon, 2026-08-19

> **Decisions taken (jon, 2026-08-19):**
> - **8.2** → *Build mappings for the unobservable origins.* Hydrate
>   `hand_trapezoid` / `hand_capitate` / `hand_hamate` (and the tarsals, and
>   `lumbosacral_junction`) from the keypoints the tracker **does** emit, using
>   `anatomical_offset` and the other existing mapping forms. Proposal to be
>   presented before it is authored.
> - **8.3** → **Palms down, VRM 1.0 default.**
> - **8.4** → *Fix everything that is broken.*
> - Doc location → `freemocap/current-work-plans/`.
>
> The original questions are preserved below for the record.

**8.1 — `exact`/`approximate` in the mapping layer.** Ontology decision #2
retired `exact`/`approximate` in favour of primary/twist and says "No `kind`
field." skellytracker's `anatomical_offset` frames still require exactly one
`kind: exact` and one `kind: approximate`. Is that (a) a *different* concept that
legitimately keeps the old words — the mapping's own construction frame, not a
segment frame — or (b) drift that should be renamed? If (a), the vocabulary
collision is worth a note in the glossary. Separately: is
`coordinate_frame_ops.build_segment_frame` (which still dispatches on `AxisKind`
from the retired `segment_definition.py`) meant to be deleted with the rest of
the old system, or resurrected?

**8.2 — Unobservable joint origins.** `hand_trapezoid` / `hand_capitate` /
`hand_hamate` and the seven tarsals are the declared `origin_landmark`s of
segments that no tracker can hydrate. Three options, and it changes the fix:
(a) keep them and let a real IK/constraint pass place them (the ontology's
"IK where not measured" — but that layer is `[FUTURE]`);
(b) re-anchor those metacarpals/metatarsals onto the wrist / ankle so every
linkage sits on a measurable point;
(c) keep them and accept a pure rigid extrapolation from the carpus/tarsus fit.
Which is the intent?

**8.3 — Hand/foot T-pose convention.** For §2.5 I need to know your canonical
T-pose: palms **down** (VRM 1.0 default — my assumption, and what my proposed
`[-1,0,0]` ulnar twist encodes) or palms **forward**? And are `foot.yaml`'s
metatarsal/phalanx lengths (18/20/21/33/30 mm, ~⅓ of real) deliberate
placeholders, or a units/authoring slip?

**8.4 — Scope of the fix.** Do you want me to (a) hand you a precise patch set
you apply, (b) apply the fixes on disk in your checkouts for you to review and
commit yourself, or (c) stop at this document? You said don't change the plans —
I've changed nothing anywhere. I'd like to confirm before touching code.

---

## 9. What I'd do, in order

1. **`skeleton_rigidifier.py:25` — replace `_FALLBACK_DIRECTION` with the
   per-segment T-pose rest direction.** This is the whole ballgame: 77 broken
   segments → 0, 147 mm → 0.0 mm, one change. §2.3.
2. **Make `TreeRigidifier` build once, not per frame** — or make it genuinely
   stateless and delete the `_last_direction` docstring that lies. Right now it's
   neither. §2.4.
3. **Repair `test_solver_keypoint_declared.py`** against the `(result, state)`
   API, and **add an end-to-end identity-at-T-pose test** that feeds only the
   mapping-producible landmark subset — i.e. exactly the table in §2.1. That test
   is the regression gate for #1 and #2, and its absence is why this shipped. §6.
4. **Turn CI on for `development-streaming`** in all three repos; add a test
   workflow to skellyforge, which has none. §6.
5. **Fix `hand.yaml`'s rest directions** (pending §8.3) — restores
   `identity == T-pose` at the wrist and restores left/right mirroring. Not
   urgent for the viewer; blocking for VMC/VRM and for any joint-angle output. §2.5.
6. **Make `align_point_sets_kabsch` actually detect degeneracy** (smallest
   singular value vs. a tolerance) and **stop swallowing it** at both call sites.
   Then decide what the pelvis should do about its three collinear points. §3.1.
7. **Give the four duplicate linkages unique identities**, and **put the hand
   into the arm chain** (`arm: {start: clavicle, end: hand}`) so it stops being
   the only segment pair outside the chain layer. §3.2, §3.3.
8. **Reconcile the docs** against the ledger in §4 — the branch is ~8 commits
   past the last doc refresh and the "DONE (identity-at-T-pose green)" line is
   the one that matters most.
