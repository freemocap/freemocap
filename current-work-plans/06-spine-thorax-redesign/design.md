# Spine & Thorax Redesign — COCO-Anchored Trunk

Status: APPROVED, in implementation. Companion to
[../ontology.md](../ontology.md) and [05-linkage-chain](05-linkage-chain-design.md).

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

## The new layout

```
pelvis (ROOT, origin = hip_center)
├─ left_pelvis   (origin = left hip socket  - TRACKED)
└─ right_pelvis  (origin = right hip socket - TRACKED)
     └─ sacrolumbar : hip_center → chest_center (~T12/L1, authored)
          └─ thoracic : chest_center → neck_center (= SHOULDER MIDPOINT, ~C7/T1)
               └─ cervical : neck_center → head_center (= MEAN OF EARS)
                    └─ skull (attaches at head_center)
```

- `neck_center` absorbs `cervicothoracic_junction` (same alias family:
  c7_t1_junction, shoulder_midpoint).
- `chest_center` absorbs `thoracolumbar_junction`.
- `head_center` replaces `craniocervical_junction` as the skull's attach
  point; it maps directly as the mean of the two ear keypoints.
- The clavicle's parent moves `chest` → `thoracic`; it connects to the
  sternoclavicular landmark, whose ANTERIOR offset (80 mm forward of the
  spine plane) is now documented authoring intent - the animation-grade
  "shoulders hang off the front of the ribcage" placement.
- `xiphoid_process` stays the thoracic segment's anterior reference
  (thoracic volume cue).

### Pelvis split mechanics

Root `pelvis` keeps the midline landmarks (hip center, sacrum_top, sacrum,
coccyx, pubic symphysis) and shrinks to a short structural root segment -
it remains the CoM anchor and tree root. `left_pelvis` / `right_pelvis`
originate at their own hip sockets (which become hemipelvis-owned, local
zero) and connect back to the root at `sacrum_top`. Sided ilium landmarks
(crest/ASIS/PSIS/SI joint) migrate into their respective hemipelvis frames,
re-authored relative to that side's hip socket.

### Naming + aliases (transition safety)

| New | Absorbs aliases |
|---|---|
| `sacrolumbar` | lumbar_spine |
| `thoracic` | chest, thorax, ribcage, thoracic_spine |
| `cervical_spine` | unchanged |
| `chest_center` | thoracolumbar_junction, t12_l1_junction |
| `neck_center` | cervicothoracic_junction, c7_t1_junction, shoulder_midpoint |
| `head_center` | craniocervical_junction |

Old references resolve through aliases during transition; nothing silently
breaks.

## Consequences for expectations

- **The trunk-immobility gate moves down one segment.** Under the new
  anatomy, `sacrolumbar` must not rotate when the arm abducts (hip-anchored);
  `thoracic` rotating slightly with the shoulder line is now CORRECT - the
  real thorax does articulate with the shoulder girdle. The freemocap gate is
  revised accordingly.
- Twist-backfill / anchoring / synthesis are definition-agnostic (they walk
  whatever joints/chains declare) - no ontology or pipeline code changes.
- Joint count changes (60 → 62: pelvis split adds one edge); chain
  declarations update (`left_leg` now starts at `left_pelvis`).

## Cascade inventory

1. `components/pelvis.yaml` + `components/spine.yaml` rewrite
2. `human_skeleton.yaml` joints + chains
3. `rest_pose.yaml` re-authored (new segments identity-oriented; carried
   entries like clavicle/upper_arm/foot orientations unchanged)
4. Tracker mappings: scaffold offset entries for `chest_center`,
   `neck_center` (+ head_center as direct mean-of-ears); regenerate ratios
   with `scripts/generate_tracker_mapping_ratios.py`
5. `center_of_mass.yaml` + `segment_mapping.py` renamed/split coverage
6. Test revisions: rest-pose origin constants, joint counts, pelvis tests,
   freemocap chest gate
7. Golden fixtures regenerate if composed channels change shape

## Acceptance gates

1. Full skellyforge suite green; probes 9/9; smoke test clean
2. FK-closure + history-independence tests green under new topology
3. Freemocap suite green with revised trunk gate
4. Viewer visual check: spine chain tracks the hip/shoulder lines without
   jumbling; abduction moves arm + slight thoracic response, sacrolumbar put
