# Spine & Thorax Redesign — COCO-Anchored Trunk

Status: **IMPLEMENTED** (with two deviations noted inline). Companion to
[../ontology.md](../ontology.md) and [05-linkage-chain](../05-linkage-chain/linkage-chain-design.md).

> **What landed vs. what this doc proposed.** The trunk re-partitioning shipped exactly as designed
> (`sacrolumbar` → `thoracic` → `cervical_spine`, neck_center = shoulder midpoint, SC anterior
> offset, xiphoid volume reference). Two deviations: (1) the **pelvis split was reverted** — the
> hemipelvis ownership/cascade tangled with the FK `connect_at` model and was deferred to `[IN]`;
> (2) the whole skeleton was then **re-authored in body-height proportions** (`H = 1.0`) rather than
> millimetres. See [../00-foundation/conventions.md](../00-foundation/conventions.md).

## The problem

The trunk's segment boundaries were authored as stacked anatomical fractions
(`sacrum_top` → `thoracolumbar_junction` → `cervicothoracic_junction`), and
every one of those junction landmarks reaches the wire as an
`anatomical_offset` computed from the shoulder/hip keypoint lines. The only
*tracked-quality* anchors in the entire torso were the hip midpoint (bottom)
and the ear midpoint (top). Errors compound hop over hop, and the visible
spine chain drifts relative to what the tracker actually sees - which is why
the 3D viewer reads as "jumbled".

Meanwhile the arm-abduction gate (`test_full_loop.py::
test_arm_abduction_rotates_humerus_and_leaves_spine`) exposed a second,
related leak: chest landmarks anchored partly to the *shoulder midpoint*
inherit arm motion into the "rigid" chest solve.

## The principle

**Segment boundaries sit on tracker-solid lines; anatomy hangs off them.**
COCO-family trackers reliably give hips (2) and shoulders (2). The trunk is
therefore partitioned at three lines that are each a mean of tracked points:

1. **hip line** - mean of the two hip keypoints (rock solid)
2. **shoulder line** - mean of the two shoulder keypoints (rock solid)
3. **head center** - mean of the two ears (rock solid)

One authored interpolation between lines 1 and 2 (`chest_center`, ~T12/L1)
is the only computed boundary. Every segment's origin is then one hop from a
tracked line, never a stack.

This stays tracker-agnostic in the constitutional sense: landmarks are still
defined by anatomical meaning ("hip center", "T12/L1 level", "head center").
What changed is the inventory: we privilege the points COCO can express as
segment *anchors*, and let non-trackable anatomy (SI joints, PSIS, xiphoid)
hang off them through mappings - which is exactly what the mapping layer is
for.

## The new layout (as landed)

```
pelvis (ROOT, origin = pelvis_origin = hip center)
├─ sacrolumbar : pelvis_origin → chest_center (~T12/L1, authored)
│    └─ thoracic : chest_center → neck_center (= SHOULDER MIDPOINT, ~C7/T1)
│         └─ cervical_spine : neck_center → craniocervical_junction
│              └─ skull (origin = head_center, attaches at craniocervical_junction)
│         └─ clavicle : sternoclavicular → acromion (off the front of the thoracic)
│              └─ upper_arm → lower_arm → carpals
└─ upper_leg → lower_leg → foot → toes  (off the pelvis at the hip sockets; ×2)
```

- `neck_center` absorbs `cervicothoracic_junction` (same alias family:
  c7_t1_junction, shoulder_midpoint).
- `chest_center` absorbs `thoracolumbar_junction`.
- The skull's own origin landmark is `head_center` (foramen magnum center),
  which maps directly as the mean of the two ear keypoints; the cervical
  spine terminates at `craniocervical_junction`, where the skull attaches.
- The clavicle's parent moves `chest` → `thoracic`; it connects to the
  sternoclavicular landmark, whose ANTERIOR offset (0.0486 H forward of the
  spine plane) is now documented authoring intent - the animation-grade
  "shoulders hang off the front of the ribcage" placement.
- `xiphoid_process` stays the thoracic segment's anterior reference
  (thoracic volume cue).

### Pelvis split (deferred - reverted)

The pelvis split was attempted and **reverted**: `left_pelvis` / `right_pelvis`
originating at their own hip sockets tangled the hemipelvis ownership/cascade
with the FK `connect_at` model. The root `pelvis` stays whole - it keeps the
midline landmarks (hip center, sacrum_top, sacrum, coccyx, pubic symphysis)
plus the sided ilium landmarks (crest/ASIS/PSIS/SI joint), and is the CoM
anchor and tree root. Deferred to `[IN]` in
[../IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

### Naming + aliases (transition safety)

| New | Absorbs aliases |
|---|---|
| `sacrolumbar` | lumbar_spine |
| `thoracic` | chest, thorax, ribcage, thoracic_spine |
| `cervical_spine` | unchanged |
| `chest_center` | thoracolumbar_junction, t12_l1_junction |
| `neck_center` | cervicothoracic_junction, c7_t1_junction, shoulder_midpoint |

`head_center` and `craniocervical_junction` are **distinct** landmarks — the skull's
own origin vs. the cervical spine's distal terminus where the skull connects — not
aliases. Old references resolve through aliases during transition; nothing silently
breaks.

## Consequences for expectations

- **The trunk-immobility gate moves down one segment.** Under the new
  anatomy, `sacrolumbar` must not rotate when the arm abducts (hip-anchored);
  `thoracic` rotating slightly with the shoulder line is now CORRECT - the
  real thorax does articulate with the shoulder girdle. The freemocap gate is
  revised accordingly.
- Twist-backfill / anchoring / synthesis are definition-agnostic (they walk
  whatever joints/chains declare) - no ontology or pipeline code changes.
- Joint count is unchanged (60) - the pelvis split (which would have added
  the `left_pelvis`/`right_pelvis` pair) was reverted; chains are as declared
  in `human_skeleton.yaml` (`spine`, `left_arm`, `right_arm`, `left_leg`,
  `right_leg`).

## Cascade inventory

1. `components/pelvis.yaml` + `components/spine.yaml` rewrite
2. `human_skeleton.yaml` joints + chains
3. `rest_pose.yaml` re-authored (new segments identity-oriented; carried
   entries like clavicle/upper_arm/foot orientations unchanged)
4. Tracker mappings: scaffold offset entries for `chest_center`,
   `neck_center` (+ head_center as direct mean-of-ears); regenerate ratios
   with `scripts/generate_tracker_mapping_ratios.py`
5. `center_of_mass.yaml` + `segment_mapping.py` renamed coverage (`chest` →
   `thoracic`, `lumbar_spine` → `sacrolumbar`)
6. Test revisions: rest-pose origin constants, joint counts, freemocap chest gate
7. Golden fixtures regenerate if composed channels change shape

## Acceptance gates

1. Full skellyforge suite green; probes 9/9; smoke test clean
2. FK-closure + history-independence tests green under new topology
3. Freemocap suite green with revised trunk gate
4. Viewer visual check: spine chain tracks the hip/shoulder lines without
   jumbling; abduction moves arm + slight thoracic response, sacrolumbar put
