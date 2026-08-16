# The FreeMoCap Kinematic Ontology

The north-star architecture for how FreeMoCap turns measured points into a standard human (and, later,
non-human) kinematic model. It exists so FreeMoCap can be a **boundary object** — one neutral core that
biomechanics, robotics, and animation each consume in their own format — and so the work we do *now* is
shaped to accept the sophisticated work we'll want *later*.

> **Read the line first.** This doc describes the *whole* ontology, but only the bottom of it is built now.
> - **Now (Definition of Done):** `keypoint → 6-DOF segment` reconstruction, realtime and posthoc,
>   producing **VMC-compatible** rotations. The immediate DoD is a **VMC-compatible *realtime* segment
>   stream**; posthoc alignment follows.
> - **Future (design for, don't build):** the constraint/solve layer — typed joints, chains, IK,
>   twist-backfill — and the URDF / OpenSim projections.
> - **Principle:** *leave the seams, don't build the rooms.* Today's segment layer is a self-contained unit
>   with interfaces shaped for what comes later; the future work attaches at those interfaces without
>   reaching back in.

## The measurement model — what we build

An observation-first stack. Each layer is defined by its own data; connection is **topological**
(parent→child), not a modeled constraint.

**Keypoint** — a measured 3D world point, tracker-named. Pure measurement, no body meaning. *(skellytracker)*

**Mapping** — the one seam: the rule that **hydrates a landmark from keypoints** (direct / weighted /
offset). Converts measurement into an observation of a model point; it does *not* define landmarks.
*(the skellytracker ↔ skellyforge interface)*

**Landmark** — a **named point in a segment's local frame**. Two faces: a *static local definition* (the
segment's shape at rest) and a *per-frame world hydration* (or absent = occlusion). The atom of the model.
*(skellyforge)*
> **Vocabulary — landmark is back, precisely.** The *old* "landmark" (a vague intermediate fitted-point
> **layer**) stays retired. The *new* landmark is a first-class, globally-named, segment-local point — the
> standard biomech/rigging usage. See [glossary](00-foundation/glossary.md).

**Segment** — an **oriented volume of space**: origin + orientation, solved from its hydrated landmarks.
Graded by how its pose is determined:
- **2 landmarks (simple):** origin + long axis directly; the roll is **not resolved** by the segment's
  own geometry — the critically-damped minimal roll carries it (see the glossary's twist tiers).
- **3+ non-collinear (complex):** full 6-DOF by best-fit (Kabsch) of the local↔world landmark clouds.
- **Rigid child (declared, not inferred):** a segment authored `rigid_with_parent` — every one of its
  landmarks is a member of its parent's landmark set, so it has no independent articulation geometry.
  Its pose is **not solved from its own hydrated landmarks**: it inherits the parent's solved pose
  composed with its authored rest local rotation (`q_world = q_parent · q_rest_local`). The head's
  eye / ear / nose segments are rigid children of the skull clique; the jaw and the mouth corners are
  **not** — they articulate and anchor at observed.

A segment's pose is always 6-DOF; what varies is how much of it the segment's own landmarks determine.
*(Decision 2026-08-14: the per-segment observed/unobserved-DOF **flag** was dropped — more machinery than
the stream needed. The graded landmark count is the seam; a segment's grade is visible directly from its
hydrated landmarks on the wire.)* *(skellyforge)*

**Skeleton** — a **rooted parent→child tree of segments**. The connection is the hierarchy edge; a **joint
angle is the derived relative orientation** `conj(q_parent) · q_child` — measured, not constrained. Chains
(root→tip limb paths) exist here only as *views* of the tree. *(skellyforge)*

## The constraint / solve model — future, seams only

This layer *operates over* the measured skeleton to refine or infer where measurement is thin. **We do not
build it now**, but the measurement model above leaves its attach points.

**Linkage** — a **typed joint model attached to a parent→child edge**: a DOF/constraint (revolute knee,
saddle thumb-CMC, spherical shoulder, planar scapula …) with limits. Where the measurement model *reads* a
joint angle, this layer *constrains* it — enabling joint-specific fits and anatomical validity. Attaches at
the hierarchy edge + the segments' landmarks.

**Chain / IK** — a solving path through the tree (FABRIK-style) that **backfills unobserved DOF** (a simple
2-landmark segment's twist inferred from its neighbours) and reconciles under-observed regions. Attaches at
the simple-segment grade — recognizable directly from the stream (2 hydrated landmarks), so no per-segment
flag is needed.

> These are the "share-a-landmark / joints / chains" ideas from earlier drafts, correctly relocated: a
> *solve* concern for the measurement-poor case, not part of the measurement core.
>
> **Stability does not wait for this layer.** The measurement stack alone — Euro filter (keypoints) →
> tree/fit rigidification → critically-damped orientation solve — stabilizes the stream today: the
> 2-landmark tree pass preserves the old skeleton-rigidifier's effect, and the 3+ per-group fits are
> strictly stronger. Settled 2026-08-14; see [02-pipeline/realtime-loop.md](02-pipeline/realtime-loop.md).

## The constitution — invariants at every layer

- **Global unique IDs**, authored as side-agnostic **types** → compiled to **instances**
  (`elbow` the type → `person0.left_elbow` the entity).
- **Compositional data + a global registry** — the registry gives O(1) validation; the data stays
  hierarchical (never flattened to get global names).
- **Two-faced landmark** — static local definition + per-frame world hydration.
- **The graded segment, not a flag** — a segment's solvability is declared by its landmarks (2 = simple,
  damped roll; 3+ = full fit; all-in-the-parent = rigid child, declared). *(An earlier
  observed/unobserved-DOF flag was dropped 2026-08-14 — the grade carries the same information and is
  recoverable from the stream itself.)*
- **Observation-first** — direct/FK where measured; IK/constraint only where not.
- **Lean core + adapters** — VMC / URDF / VRM / OpenSim / C3D / LSL are edge projections, never baked into
  the core.
- **Non-rigid representations are parallel layers** — blendshape face, eyeballs, soft tissue attach as
  separate components (ECS-style), not contorted into segments.

## The boundary — who owns what

```
skellytracker  →  [ mapping: the one seam ]  →  skellyforge            →  freemocap
  keypoints          hydrate landmarks           landmark→segment→skeleton   pipelines + adapters
```
- **freemocap has two consumers of one model:** realtime (online lengths, per-frame, damped) — *the
  now-work* — and posthoc (batch, unbounded window) — *after*.
- **Adapters project the one skeleton outward:** VMC *now*; URDF / VRM / OpenSim / BVH *later*.

## The seams the now-work must leave (and nothing more)

1. **Per-segment 6-DOF pose, graded by landmark count** (2 = simple, twist damped; 3+ = full fit). (The
   attach point for IK twist-backfill — a segment's grade is visible from its hydrated-landmark count on
   the stream, so the simple segments are findable without a per-segment flag. *(A flag was dropped
   2026-08-14; see the constitution.)*)
2. **Landmarks first-class, globally-named, segment-local.** (Attach point for joint-specific fits; the
   simple↔complex grade falls out of landmark count.)
3. **Parent-child hierarchy + derived joint angles, kept separate from estimation.** (Attach point for the
   typed-joint layer.)
4. **An output schema rich enough to project outward** — frames + hierarchy + per-frame landmark
   presence (a missing row is occlusion). VMC
   now; URDF/VRM/OpenSim later. (**URDF is the completeness checklist:** if the schema can round-trip a
   URDF, it can feed robotics + sim.)
5. **No joint constraints baked into segment estimation.** The measurement core stays pure.

## Prior art — the wheels we're re-using (deliberately)

FreeMoCap's core is the intersection of three mature lineages, and each output format is "the same skeleton,
differently serialized" — which *is* the boundary-object thesis:
- **Biomechanics** (the bedrock): ISB segment-frame construction from anatomical landmarks; OpenSim models; C3D.
- **Robotics:** URDF's link/joint/tree — the most rigorous *kinematic* serialization (joint types, axes,
  limits). The reference for the future constraint layer, and a strong export target.
- **Animation / real-time:** VRM / glTF / BVH bone hierarchies; **VMC** (the current streaming target).

---

*Status (2026-08-14):* the measurement model is mostly built — skellyforge's segment model + rigid fit +
length estimation, and freemocap's realtime stream. The now-work is making it **ontology-shaped and
VMC-complete**. Scope + progress: [IMPLEMENTATION_PLAN](IMPLEMENTATION_PLAN.md); the layer this refactor
touches: [01-data-model/segment-model.md](01-data-model/segment-model.md).
