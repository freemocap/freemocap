# Realigning skellytracker + freemocap onto the refactored skellyforge

**Goal (user-set):** get the **realtime pipeline** running on the new human skeleton. Then
re-introduce charuco to realtime. Then rebuild the posthoc pipeline on the same system.

Everything below is read off the code as it stands on disk today, not off the notes.
`current-work-plans/HANDOFF.md` and `ontology.md` describe the *previous* generation of the
model (95 segments / 146 landmarks, `primary`/`twist` axes, `rest_direction`, `JointLinkage`
and `KinematicChain` landed). None of that is true of the skellyforge on disk now.

---

## 1. What skellyforge actually is now

61 segments, 124 landmarks, 52 face blendshapes. Authored in
`skellyforge/definitions/human_skeleton/` (`human_skeleton.yaml` + 7 component files +
`rest_pose.yaml` + `face.yaml`), compiled by `SkeletonDefinition.from_yaml`.

Live API surface (`skellyforge/core/skeleton/`):

| Concern | Current | What it replaced |
|---|---|---|
| the model | `SkeletonDefinition.from_yaml` | `HumanSkeleton.standard_human()` |
| rest geometry | `RestPose.from_yaml` / `build_rest_pose` | `build_standard_human_tpose` |
| per-frame solve | `hydrate_skeleton` / `hydrate_segment` | `rigidify_landmarks` + `solve_frame_orientations` |
| roll for direction-only segments | `ContinuousRollResolver` (parallel transport) | `critically_damped_orientation` |
| subject scaling | `estimate_segment_lengths` (moved, new signature) | `kinematics.segment_length_estimation` |
| pose output | `SkeletonPose` / `SegmentPose` / `PoseSolution` | `FrameOrientationResult` |

Axes are `exact` / `approximate` again (not primary/twist). Sided entries are authored left-only
and the loader mirrors x **and negates x-axis declarations** on the right. Linkage and chain are
**placeholders** — the hierarchy currently lives in `rest_pose.yaml`'s `parent` / `connect_at`.

**Deleted outright** (confirmed via `git log --diff-filter=D`): `skellymodels/` entirely
(managers, actors, biomechanics, bvh_exporter, tracking_model_info, trajectory/Point3d),
`kinematics/inertial/` (center_of_mass, composite_inertia, ground_reference,
anthropometric_parameters), `kinematics/{orientation_solver, skeleton_rigidifier, tpose,
segment_lengths, critically_damped_orientation, quaternion_math}`, and `post_processing/`
(filters + interpolation).

---

## 2. The blocker nobody has hit yet: freemocap won't import

The mapping work is real, but it is **not** the first thing in the way. freemocap imports
**13 skellyforge module paths that no longer exist**, several of them straight down the
realtime path:

```
realtime_aggregator_node.py     skellyforge.kinematics.inertial.center_of_mass
                                skellyforge.kinematics.inertial.ground_reference
                                skellyforge.kinematics.orientation_solver
                                skellyforge.kinematics.skeleton_rigidifier
                                skellyforge.kinematics.tpose
                                skellyforge.kinematics.segment_length_estimation
                                skellyforge.skellymodels.standard_human.human_skeleton
                                skellyforge.data_models.trajectory_3d
streaming_kinematics.py         skellyforge.kinematics.inertial.composite_inertia
                                skellyforge.data_models.trajectory_3d
export_to_blender.py,           skellyforge.post_processing.{filters,interpolation}
segment_length_io.py, ...       skellyforge.skellymodels.models.tracking_model_info
```

Half of these have a direct successor in the new skellyforge (see the table above). The other
half — **center of mass, composite inertia, ground reference, anthropometric parameters,
post-processing filters + interpolation, `Point3d`, BVH export, the actor/manager layer** —
have **no successor anywhere**. That is a decision, not a port:

> **Q1. Do CoM / inertia / ground-reference / filters get rebuilt inside skellyforge (it calls
> itself "the standard human *and kinematics*"), or do they move into freemocap?**

My read: CoM and inertia are *functions of a hydrated skeleton* and belong in skellyforge next
to `skeleton_pose.py`. Filters and interpolation are *signal conditioning on keypoint streams*,
which is upstream of the skeleton entirely — those belong in freemocap (or skellytracker's
`temporal_processing/`, which already does exactly this kind of work). `Point3d` should just
die and be replaced by `spatial_vectors.Point`.

---

## 3. The mapping audit — measured, not guessed

I expanded the 124-landmark vocabulary (canonical names + aliases, with the loader's sided
expansion) and diffed every mapping YAML's target keys against it.

### Body mappings — `mediapipe_body` and `rtmpose_body` (identical target sets, by design)

40 targets each → **22 exact, 5 resolve only through an alias, 13 name nothing at all.**

**Alias-only (works, but should be canonicalized so the YAML reads like the model):**

| mapping key | canonical landmark |
|---|---|
| `left_hip` / `right_hip` | `left_hip_socket` / `right_hip_socket` |
| `hips_center` | `pelvis_origin` |
| `neck_center` | `cervicothoracic_junction` |
| `lumbosacral_junction` | `sacrum_top` |

**Dead targets (13) and where they should go:**

| dead key | proposed |
|---|---|
| `jaw` | `chin` (alias `menton`) |
| `mid_sternum` | `sternoclavicular_notch` (alias `suprasternal_notch`) — the offset already lands there |
| `trunk_center` | no landmark exists. Either drop it, or point at `thoracolumbar_junction` (alias `chest_center`) — but the current recipe is the shoulder+hip 4-point mean, which is *not* T12/L1 |
| `left_mouth` / `right_mouth` | nearest is `left/right_canine_tooth_tip`. Semantically wrong (mouth corner ≠ canine tip). Recommend dropping until a mouth landmark is authored |
| `left/right_foot_calcaneus` | `left/right_calcaneus` |
| `left/right_foot_ball` | `left/right_ball` |
| `left/right_foot_big_toe_tip`, `left/right_foot_pinky_toe_tip` | the foot was collapsed to **one** `TOE_TIP` per side ("tip of the longest toe (second toe)"). Four keys collapse to two |

> **Q2.** `toe_tip` is the second toe. RTMPose gives `big_toe` + `small_toe`; MediaPipe gives one
> `foot_index`. Mean the two on RTMPose and pass `foot_index` through on MediaPipe? Or bias toward
> big toe? (The mean is anatomically closer to the second toe, so that's my default.)

### Hand mappings — `mediapipe_hand` and `rtmpose_hand`

**40 of 40 targets dead, both files.** The naming scheme changed wholesale:

```
left_hand_index_finger_metacarpophalangeal_joint  ->  left_index_mcp
left_hand_index_finger_proximal_interphalangeal…  ->  left_index_pip
left_hand_index_finger_distal_interphalangeal…    ->  left_index_dip
left_hand_index_finger_tip                        ->  left_index_tip
left_hand_thumb_interphalangeal_joint             ->  left_thumb_ip
left_hand_trapezium                               ->  left_trapezium
```

These two files are a mechanical rename — cheap. What is *not* mechanical: the new hand also
declares `carpal_origin`, five `*_cmc` landmarks, and 8 named carpals per side, and **no tracker
emits any of them**. See §4.

---

## 4. The hydration audit — this is the number that matters

`hydrate_segment` needs, per segment, either 3+ observed owned landmarks (rigid fit) or **both
its `reference_geometry.origin` and its `exact`-axis landmark**. I computed that for all 61
segments against what the body mappings produce today:

**8 of 61 segments hydrate.** `pelvis`, `skull`, `left/right_upper_arm`, `left/right_lower_arm`,
`left/right_lower_leg`. Everything else raises.

**64 landmarks are missing.** Grouped by the work that fixes them, in dependency order:

| # | Missing landmarks | Unblocks | Effort |
|---|---|---|---|
| 1 | `thoracolumbar_junction`, `craniocervical_junction` | `lumbar_spine`, `chest`, `cervical_spine` (3) | 2 new `anatomical_offset` entries |
| 2 | `left/right_hip_joint` | `left/right_upper_leg` (2) | trivial — this is the same physical point as `hip_socket`, just owned by `upper_leg` instead of `pelvis`. Emit both keys from the same source |
| 3 | `left/right_acromion` | `left/right_clavicle` (2) | the tracker's `*_shoulder` keypoint **is** acromion-ish. Decide (Q3) |
| 4 | `ankle_origin`, `calcaneus`, `ball`, `toe_tip` ×2 | `heel`, `foot`, `toes` (6) | mostly renames of existing entries + `ankle_origin` (same point as `ankle`, different owner — like #2) |
| 5 | `carpal_origin`, 5× `*_cmc`, all `*_mcp/pip/dip/tip` ×2 | 42 hand segments | the hand rewrite, §3 |

Doing 1–4 takes the realtime skeleton from **8 → 21 segments**, which is the whole body minus
hands. That is the realtime milestone.

> **Q3.** `left_shoulder` (glenohumeral, owned by `upper_arm`) and `left_acromion` (owned by
> `clavicle`) are two distinct landmarks in the model, and the tracker has one keypoint that is
> physically closer to the acromion. Pass the keypoint straight to both? Or keep the passthrough
> on `shoulder` and add a small `anatomical_offset` for `acromion`?

> **Q4.** `neck_center` is currently the **shoulder midpoint**, and it aliases to
> `cervicothoracic_junction` (C7/T1). The shoulder midpoint sits anterior and inferior to C7/T1.
> This alias is load-bearing — `chest`'s exact axis is `cervicothoracic_junction`, so the whole
> thorax orientation rides on it. Worth an `anatomical_offset` rather than a passthrough.

---

## 5. Where the mapping layer should live

`ontology.md` calls mapping "the one seam" between skellytracker and skellyforge. On disk the
YAMLs live in **skellytracker**, but their *keys* are **skellyforge's vocabulary**, and
skellytracker has **zero** code dependency on skellyforge (only two docstring mentions). So
nothing validates the seam — which is exactly why four files drifted into 66 dead target names
with no test failing.

> **Q5. Three options:**
> - **(a)** Mapping YAMLs move to **freemocap**, which already imports both sides. skellytracker
>   goes back to emitting keypoints and nothing else. Cleanest against the stated boundary rule.
> - **(b)** Stay in skellytracker, and freemocap owns a validation test. Smallest diff.
> - **(c)** skellytracker takes a light dependency on skellyforge (just the YAML + loader) and
>   validates at load. Breaks the "standalone" framing least usefully.
>
> My recommendation is **(a)**. Mapping is the seam, and freemocap is the only repo that is
> allowed to see both sides of it.

Either way, **`TrackerMapping.__init__` should grow a `known_landmark_names` check** mirroring the
`known_tracker_keypoints` check it already has. It validates one direction of the seam and not the
other, which is precisely the half that broke.

---

## 6. Proposed order of work

### Stage 0 — make freemocap import again *(the gate; nothing else can be tested until this is done)*
1. Answer Q1. Port or relocate every dead skellyforge import.
2. Re-point the realtime aggregator: `HumanSkeleton.standard_human()` → `SkeletonDefinition.from_yaml`;
   `build_standard_human_tpose` → `RestPose`; `rigidify_landmarks` + `solve_frame_orientations` →
   `hydrate_skeleton` + `ContinuousRollResolver`; `Point3d` → `spatial_vectors.Point`.
3. Rewrite `HANDOFF.md` / `ontology.md`'s status section — they currently document a model that
   no longer exists, and they will mislead the next pass through this code.

### Stage 1 — canonicalize the two body mappings
Rename the 5 alias targets to canonical names; fix the 13 dead ones per §3. Keep the two files
target-identical (that invariant is stated in the YAML comments and is worth keeping).

### Stage 2 — the missing body landmarks *(§4 items 1–4)*
Spine junctions, `hip_joint`, `acromion`, foot chain. **8 → 21 hydrating segments.**

### Stage 3 — the guard rail
A test that loads every mapping YAML, asserts every target resolves against
`SkeletonDefinition`'s landmark vocabulary, and prints the per-segment hydration table from §4.
This is the artifact that keeps the seam from drifting again. (Placement depends on Q5.)

### Stage 4 — the hand mappings
The rename, plus `carpal_origin` / `*_cmc`. 42 more segments.

### Stage 5 — charuco back into realtime.
### Stage 6 — posthoc rebuilt on the same path.

---

## 7. Recommended immediate next action

Stage 0 step 1 — **answer Q1** (where CoM / inertia / ground-reference / filters live), because
it decides whether the aggregator's next 200 lines are a port or a delete. Everything downstream
is mechanical once that's settled.

If you'd rather see motion first: Stages 1 + 2 are self-contained inside the four mapping YAMLs
and can land before Stage 0 — they just can't be *run* until freemocap imports.
