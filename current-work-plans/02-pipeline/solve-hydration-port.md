# Solve + Hydration Port

**Status: the plan for the next skellyforge work.** The new ontology classes
(`AnatomicalLandmark` / `RigidBodySegment` / `JointLinkage` / `KinematicChain` /
`HumanSkeleton` / `FaceBlendShapes`) and the flat YAML definitions are **landed** (50 segments,
49 linkages, 15 chains — audited green). The next step wires them into the solve: build the T-pose,
hydrate landmarks from keypoints, solve segment poses, derive lengths, then delete the old system.

## Why this, why now

`orientation_solver.py` + `reference_geometry.py` are written against the old `SegmentDefinition` +
swing+twist. The new model is a cleaner shape: **positions**, **objects**, and the **full rigid-body
skull**. The port is what makes the new model *actually solve* — until it lands, the YAML is inert data. This is the keystone: everything downstream
(realtime, posthoc, VMC, adapters) consumes this solve.

## The entity / action boundary (the contract)

**Entities are frozen data + pure accessors; actions are separate typed functions.** No solver, IK, or
twist resolution is a method on an entity.

- **On the entity (allowed):** pure accessors that *view / measure* without mutating —
  `RigidBodySegment.length`, `KinematicChain.segments`. Properties, not behavior.
- **Separate (required):** anything that *mutates / converts / builds / solves* — the T-pose build, landmark
  hydration, the pose solve, and (later) IK / FK / twist. These are free functions in `kinematics/`.
- **No state-carrying "solver" class.** State flows in and out explicitly (`state: SolveState` in,
  `(result, state)` out) — every action stays stateless + testable.
- **Aggressive typing, no `Any`.** The only `cast` is at the YAML edge (`yaml.safe_load`); `load_config` is a
  generic `TypeVar` transform, not `Any -> Any`.

### Module layout

```
skellyforge/
├── skellymodels/standard_human/   # ENTITIES — frozen data + accessors only
│   ├── anatomical_landmark.py
│   ├── rigid_body_segment.py      #   .length        = accessor (measurement)
│   ├── joint_linkage.py
│   ├── kinematic_chain.py         #   .segments      = accessor (view)
│   ├── human_skeleton.py          #   .from_yaml     = construction (allowed)
│   ├── face_blendshapes.py
│   └── config_types.py
└── kinematics/                    # ACTIONS — typed free functions
    ├── coordinate_frame_ops.py    #   Gram-Schmidt, Kabsch (primitives)
    ├── quaternion_math.py
    ├── critically_damped_orientation.py
    ├── tpose.py                   #   build_standard_human_tpose(...)
    ├── orientation_solver.py      #   solve_frame_orientations(...)
    └── (later) chain_ik.py, twist_resolution.py, fk.py
```

### Function signatures

```python
def build_standard_human_tpose(skeleton: HumanSkeleton) -> StandardHumanTPose: ...

def solve_frame_orientations(
    skeleton: HumanSkeleton,
    tpose: StandardHumanTPose,
    landmarks: dict[str, NDArray[np.float64]],   # hydrated landmark world positions
    *,
    timestamp_seconds: float,
    state: SolveState,
) -> tuple[FrameOrientationResult, SolveState]: ...

# future actions — same shape (stateless, typed)
def solve_chain_ik(chain: KinematicChain, target: NDArray[np.float64], ...) -> ...: ...
def resolve_twist(segment: RigidBodySegment, ...) -> ...: ...
```

## State (the result / state split)

A stateful action returns a `(result, new_state)` pair — the **result** is the per-frame output, the
**state** is the action's memory across frames. They are separate frozen types:

```python
@dataclass(frozen=True, slots=True)
class FrameOrientationResult:                       # RESULT only — no state
    world_quaternions: dict[str, NDArray[np.float64]]
    local_quaternions: dict[str, NDArray[np.float64]]

@dataclass(frozen=True, slots=True)
class OrientationSolveState:                        # per-segment damped-filter memory
    damping_states: dict[str, CriticallyDampedOrientationState]

    @classmethod
    def empty(cls, skeleton: HumanSkeleton) -> "OrientationSolveState": ...
```

The whole envelope is a nested `SolveState` — one slice per action, so future actions (twist, IK) each get
their own slice instead of inventing an ad-hoc "previous" argument:

```python
@dataclass(frozen=True, slots=True)
class SolveState:
    orientation: OrientationSolveState
    twist: TwistResolutionState | None = None
    chain_ik: ChainIkState | None = None
```

**Why explicit, frozen, serializable state** (the skellytracker borrow — see
`skellytracker/rearchitecture-docs/skellytracker-architecture/06-tracker-state.md`): it is inspectable,
resumable, and testable, and it never hides mutable state on the entity or a "solver" object. Frozen is
*stricter* than skellytracker's mutable-by-convention — immutable by construction.

## The two faces (the spine of the whole design)

Every layer has a **static face** (authored once, in YAML) and a **hydrated face** (computed per frame):

- **landmark** — static: `rest_position` in its `reference_frame`; hydrated: a world position.
- **segment** — static: rest geometry (origin / basis / length); hydrated: the pose (origin + orientation).
- **linkage / chain / skeleton** — static: the tree / paths; hydrated: joint angles / chain poses.

The solve maps static → hydrated, per frame, with `identity == T-pose`.

## Step 1 — the T-pose build (`StandardHumanTPose`)

Port `reference_geometry.py` onto the new classes. For each `RigidBodySegment`, build its **reference
geometry** (the per-segment origin/basis/length — a part of the segment):

- **origin** = the `origin_landmark`'s rest position (authored in the parent's local frame).
- **distal** = the primary direction's `target_landmark` rest position (authored in the segment's own frame).
- **length** = `|distal − origin|` — **derived from the rest positions** (subject scaling = a uniform
  scale of every `rest_position`).
- **basis** = the rest frame: Gram-Schmidt the primary direction (hard seed) + the twist direction (soft
  hint) (`coordinate_frame_ops.assemble_named_basis` / `build_segment_frame`).

Then compose the segment transforms root→leaf to get every landmark's **rest-world position**. That whole
structure is `StandardHumanTPose` — the thing the orientation solver measures against, and the thing that
feeds the rest-pose message.

**Why positions:** the landmark's `rest_position` *is* the anatomical fact; the length is a
*consequence* of it.

## Step 2 — landmark hydration (mostly unchanged, re-pointed)

The **mapping** (skellytracker, see
[tracker-mapping.md](../01-data-model/tracker-mapping.md)) produces landmark world positions from keypoints
(direct / mean / weighted / `anatomical_offset`). The **rigidifier** (freemocap
`skeleton_rigidifier.py`, see [realtime-loop.md](realtime-loop.md)) rigidifies them — the MDS template +
rotation-only Procrustes for the skull, the 2-landmark tree pass elsewhere. The result is the per-frame
**hydrated** landmark world positions.

This step already runs; the port re-points its output onto the new landmark **objects** (and the new
`pelvis`/`trunk_center` names) rather than changing its math.

## Step 3 — the solve (`solve_frame_orientations` port)

For each segment, in hierarchy order:

- **3+ landmarks (full rigid body)** — solve the world rotation by **Kabsch**
  (`coordinate_frame_ops.align_point_sets_kabsch`): align the segment's rest landmark cloud → its live
  landmark cloud. Over-determined, so **no twist ambiguity, no damping**. The head is the 7-point skull;
  hips / feet / toes are likewise full rigid bodies.
- **2 landmarks (simple)** — swing (`rotation_between_vectors` on the primary direction) + the
  critically-damped minimal roll (`critically_damped_orientation.py`).
- **rigid child** (`rigid_with_parent`) — inherit the parent's world rotation; no independent solve.
- **local** = `conj(q_parent) · q_child` (the D1 convention, [conventions.md](../00-foundation/conventions.md)).

**Why Kabsch for 3+:** the full cloud over-determines the rotation — this is the "solve the skull as ONE
rigid body from all its pairwise landmark geometry" decision, and it is what kills the per-frame flip the
2-point swing+twist suffered (see [kinematics-engine.md](kinematics-engine.md) + [ontology.md](../ontology.md)).

## Step 4 — delete the old system

After the port lands and tests are green, excise: `segment_definition.py`, `reference_geometry.py`,
`rest_pose.py`, `body_part.py` / `hand_part.py` / `face_part.py` / `standard_human_model.py`, plus
`skellymodels/models/` + `managers/` + `tracker_info/*.yaml`.

**Careful:** the wire projection (`RestSegment` / `RestLandmark` in `rest_pose.py`) is consumed by the
message model — **port it** onto the new classes before deleting, don't delete it blind.

## The math (all already on disk + tested)

- **Kabsch/Umeyama** — `coordinate_frame_ops.align_point_sets_kabsch` (det=+1, reflection-corrected).
- **Gram-Schmidt frame** — `coordinate_frame_ops.build_segment_frame` / `assemble_named_basis`.
- **Critically-damped filter** — `critically_damped_orientation.py` (framerate-independent, time-constant based).
- **Conventions** — `wxyz`, `identity == T-pose`, `conj(q_parent)·q_child` ([conventions.md](../00-foundation/conventions.md)).

## Testing (see [testing-strategy.md](../00-foundation/testing-strategy.md))

- **Identity at T-pose** — feed the rest positions back as live input; every segment solves to identity
  (world AND local). The load-bearing model test.
- **Round-trip** — a known rigid rotation of the rest cloud; Kabsch recovers it exactly.
- **Mirroring** — the right side is Y-negated; the basis stays right-handed (`det = +1`).
- **Loader** — `HumanSkeleton.from_yaml` composes parts, resolves references, mirrors, derives lengths
  (already green: `skellyforge/tests/test_lower_body_skeleton.py`).

## Cross-references

- Ontology (seven layers + two faces): [ontology.md](../ontology.md).
- Definition (YAML + classes): [segment-model.md](../01-data-model/segment-model.md).
- T-pose: [reference-geometry.md](../01-data-model/reference-geometry.md).
- Solve: [kinematics-engine.md](kinematics-engine.md).
- Lengths: [segment-length-estimation.md](segment-length-estimation.md).
- Hydration (mapping): [tracker-mapping.md](../01-data-model/tracker-mapping.md).
- The loop: [realtime-loop.md](realtime-loop.md).
- Conventions: [conventions.md](../00-foundation/conventions.md).
- Testing: [testing-strategy.md](../00-foundation/testing-strategy.md).
