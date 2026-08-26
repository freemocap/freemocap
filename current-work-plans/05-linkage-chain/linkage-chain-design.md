# Linkage & Chain Layers — Design Plan

Status: PROPOSAL (not yet implemented). This document defines what layers 5–6 own,
how they get built, and the invariants that prove them correct. It extends
[ontology.md](../ontology.md) — read that first for the layer definitions.

---

## 1. Why these layers exist

Segments (layer 4) answer "where is each rigid body?" — absolute poses in world.
They cannot answer the questions users actually ask:

- **Clinical:** "how much left-knee flexion?" — a *relative* quantity between two
  segments, expressed in a named convention with defined signs.
- **Synthesis:** "given joint angles, where does the hand land?" — forward
  kinematics across many segments.
- **Completion:** "the wrist is tracked but the elbow is occluded — where is it?"
  inverse kinematics over a chain; "the hand rotated 40° — how much was
  forearm pronation?" — twist inference along a chain.

Each question belongs to its layer: relative math at the **linkage**, multi-segment
math at the **chain**. Neither reaches upward; biomechanics and adapters consume
both.

## 2. Layer 5 — linkage (the joint layer)

A **linkage** is two segments joined at the landmark they share (the child's
`connect_at`). Its static face is a **joint definition**; its hydrated face is a
**joint pose**; its math is **relative orientation and its decomposition into
named angles**.

### 2.1 Static face — `JointDefinition`

Authored in YAML (see §5 for where), one entry per parent→child edge:

```yaml
joints:
  left_elbow:
    parent: left_upper_arm        # proximal segment
    child: left_lower_arm         # distal segment
    connect_at: left_elbow_landmark_name   # the shared point (today: child's connect_at)
    type: ball                    # ball | hinge | universal | fixed  (default: ball)
    convention:
      sequence: zyx               # euler decomposition order applied to q_rel
      angle_names: [flexion_extension, abduction_adduction, pronation_supination]
      zero_pose: tpose            # what configuration reads as all-zeros
```

Rules carried over from the constitution: global unique IDs; object references
after load (a `parent` naming a nonexistent segment fails the load at that line);
frozen dataclasses with fail-loud `__post_init__` validation.

**Convention metadata is data, not code.** The decomposition function is generic;
per-joint YAML picks the sequence, the names, and the signs. Refining a joint to
exact ISB/Grood-&-Suntay spec later is a YAML edit with citations in comments —
never a code change.

### 2.2 Hydrated face — `JointPose`

Per frame, per edge:

| field | meaning |
|---|---|
| `relative_orientation` | `conj(q_parent) · q_child` — full 3D relative rotation |
| `angles` | the decomposed triple, in the joint's convention, in radians |
| `provenance` | which `PoseSolution`s fed parent and child |

**Provenance is mandatory.** 56 of 61 segments are direction-only; any angle
computed through a transported-roll input is partly convention, not measurement.
Every exported angle states what it stands on. A consumer comparing sessions must
be able to see that `shoulder_axial_rotation` is transport-carried while
`knee_flexion` comes off fully-measured geometry. This is the honesty mechanism —
without it the numbers look more measured than they are.

### 2.3 Math owned by linkage (and nothing else)

- `relative_orientation(parent_pose, child_pose)` — closed form.
- `decompose(relative_orientation, convention)` → named triple; and its exact
  inverse `compose(angles, convention)` → relative orientation.
- Angle continuity helpers (unwrap across frames).

Explicitly **not** linkage math: anything spanning >2 segments, anything needing
landmark positions rather than segment poses, any solver with iteration.

## 3. Layer 6 — chain (the multi-segment layer)

A **chain** is a declared path/tree over linkages (`start` → … → `end`). Static
face: chain declarations referencing joint names. Hydrated face: a `ChainPose`
(ordered segment poses + joint angles). Its math:

1. **Forward synthesis** — joint-angle series → segment poses and landmark
   positions. Generalizes the existing rest-pose FK from one static pose to
   time-varying angles. Primary consumers: synthetic-data generation for tests,
   animation export.
2. **Inverse kinematics** — targets → joint angles. Position-level FABRIK for
   reach chains; closed-form two-bone for limbs; orientation-aware variants where
   the end segment carries a measured orientation. Every solve reports residuals;
   fail-loud on unreachable targets (no silent clamping).
3. **Twist backfill** — estimating axial rotation along a chain from downstream
   measurements: the wrist/hand landmarks observe what the elbow↔wrist pair
   cannot (see §7). This upgrades roll handling from pure convention toward
   observation wherever information actually exists.
4. **Coupled constraints** — authored ratio couplings (finger MCP:PIP ≈ 1:2)
   enforced during synthesis/backfill. Later phase; declared in chain YAML when
   needed.

## 4. What happens to `ContinuousRollResolver`

Two resolution tiers now live there (L6.2 ✅):

- **Skeleton level (`resolve_pose`, production path):** a direction-only
  segment's roll is ANCHORED - the secondary axis is projected perpendicular
  from the direction pointing back toward the parent segment's origin, which is
  roll-free measured geometry. Same motion ⇒ same roll, regardless of history.
  Falls back to parallel transport when the parent pose is absent or the hint
  is collinear with the long axis (straight chains carry no roll reference at
  all - that is information, not a failure).
- **Segment level (`resolve_segment_pose`):** pure parallel transport, the
  historical primitive, available without context.

The carry updates on BOTH paths so fallback frames continue from the last
anchored state. Twist backfill from end-segment orientations remains L6.4.

## 5. Topology reconciliation — one home for the tree

Today the hierarchy lives twice in spirit: `rest_pose.yaml` holds
`parent`/`connect_at` (geometry-adjacent), while the ontology says the linkage
layer owns joints. Resolution, following the single-source rule:

- `human_skeleton.yaml` gains a `joints:` section (the §2.1 schema) — **the**
  authoritative topology. `rest_pose.yaml` keeps only per-segment rest
  orientations and loses `parent`/`connect_at`.
- `SkeletonDefinition` compiles `SegmentLinkage` objects at load; `RestPose`
  reads the parent tree from the linkage instead of its own fields.
- Loader validations move with it: single root, every segment has exactly one
  parent edge, `connect_at` owned by the parent, acyclicity — all asserted
  against joint definitions now, error messages pointing at the joint YAML line.

## 6. Invariants — how we know it is right

Executable, not aspirational. Each lands with its layer:

1. **Determinism:** the same observations through a reset resolver produce
   identical angles, every time - reproducibility is what makes an angle
   publishable.
2. **Decompose/compose round trip:** `compose(decompose(q_rel)) == q_rel` to
   tolerance, for every one of the twelve valid joint conventions shipped,
   across random quaternions and forced gimbal locks (L5.1: done -
   `test_euler_sequence.py`).
3. **FK closure (the crown jewel, L6.1):** synthesize a motion from random-but-valid
   joint-angle series via chain FK → render its landmarks through hydration →
   recover poses → decompose → **angles match the synthesized inputs**. This one
   property ties layers 3–6 into a single verified loop and is the standing
   regression net for every future change to any layer in it.
4. **Tracking invariants (done - `test_linkage_pose.py` + probes):** each
   segment's authored relative orientation sends its local origin→primary
   displacement direction onto the world displacement direction; hydrated
   primary axes track the bone at 0° error under scripted motions.
5. **Provenance propagation (done):** an angle computed through any transported
   input reports so in `JointInputProvenance.fully_measured` - tested, not
   documented-and-hoped.

A note on "T-pose zeros": the shipped T-pose authors several NON-identity rest
orientations (the legs' half turn, the clavicle's posterior tilt), and a
direction-fit parent initializes transported roll from a deterministic
perpendicular - so rest-pose angles are *deterministic conventions*, not zeros.
That is exactly what `convention.zero_offsets` exists to override per joint when
a clinical zero differs from the authored pose; it is authored data, not an
assumption.

## 7. Known limits stated plainly

- Two collinear landmarks cannot see axial twist between them. Pronation remains
  convention (transport) until twist backfill has downstream observations to use.
  Angles whose value depends on such inputs carry provenance saying so.
- Ball-joint Euler triples have singularities (gimbal configurations); the
  convention metadata names the sequence so users know where the singularity sits,
  and `relative_orientation` (quaternion) is always available alongside the
  decomposed angles.
- No forces, torques, or dynamics anywhere in these layers — dynamics-derived
  quantities remain in `core/biomechanics/`.

## 8. Phases

| Phase | Delivers | Test gate |
|---|---|---|
| L5.1 ✅ | `JointDefinition` YAML + compilation; topology moved out of `rest_pose.yaml`; `relative_orientation` + generic euler `decompose/compose`; provenance struct | invariants 2, 4, 5; full suite green |
| L6.1 ✅ | Chain declarations (`chains:` YAML, compiled with contiguity validation); forward synthesis over the whole joint tree | invariant 3 in its honest two-tier form: exact closure for every rigid-rigid joint, direction closure for ALL joints at 1e-6°; determinism; root-placement invariance. Note: the shipped model currently has NO adjacent rigid-rigid pair (rigid segments are isolated), so the exact tier is wired to the statics and exercises vacuously until one exists - asserted, not skipped |
| L5.2 | Named-angle outputs surfaced (aggregator message field; wire channel decision separate) | round trip through serialization |
| L6.2 ✅ | Anchored secondary axes: skeleton-level resolution anchors a direction segment's roll to its parent's origin direction when usable (deterministic per frame), falling back to parallel transport on degeneracy or missing parent | same-motion-same-roll history independence tested at 1e-6°; perpendicularity/handedness asserted; straight-limb and missing-parent fallbacks tested; full suite green |
| L6.3 ✅ | Two-bone analytic solver + FABRIK, both fail-loud: unreachable targets raise naming distances; FABRIK exhaustion raises naming its residual; out-of-reach stretch only with explicit permission and reports `converged=False` | reach probes: known triangles solved exactly; bone lengths preserved to 1e-9; two-bone solution is a FABRIK fixed point (1-pass convergence); unreachable/fold-limit/exhaustion raise |
| L6.4 | Twist backfill from end-segment orientations; finger couplings | pronation probe: forearm twist recovered when hand is rigid-fit |

## 9. Open decisions (need owner input before L5.1)

1. **Convention authority:** ship pragmatic per-joint euler defaults now with
   ISB-exact refinement as YAML iteration (recommended), or block on a full ISB
   pass up front?
2. **Topology move timing:** relocate `parent`/`connect_at` in L5.1 (single
   source immediately, touches loader + rest-pose tests), or alias-duplicate for
   one phase (violates single-source temporarily)?
3. **Resolver default:** once anchored secondary axes exist (L6.2), do they
   become the default for all direction segments with transport as fallback
   (recommended — deterministic), or stay opt-in?
4. **Realtime vs export:** do joint angles ride the realtime wire early (new
   channel kind, UI/debug value) or land export-first (CSV/adapters) with the
   wire later?
