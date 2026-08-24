# The Kinematics Engine

**Describes:** the math kernel + the closed-form pose solve — how observed landmark positions become
segment poses. Vocabulary in [../00-foundation/glossary.md](../00-foundation/glossary.md); the live
loop that drives it in [realtime-loop.md](realtime-loop.md).

## Where it lives

`skellyforge/skellyforge/core/` (the old `kinematics/` package is gone):

- `math/geometry/` — the affine algebra: `RotationQuaternion` (wxyz; slerp, angular velocity,
  resample, batching), `Transform` (rotation + translation), typed `Point` / `Displacement` /
  `UnitVector`, `OrthonormalBasis` + `calculate_orthonormal_basis` (+ `SpatialAxis`, `Handedness`,
  `ReferenceFrameDefinition`), `PointRingBuffer` (zero-copy streaming window),
  `numeric_tolerances.py` (the single source of every tolerance — no bare `1e-10` anywhere).
- `math/kinematics/` — closed-form solvers on observed positions: `rigid_point_set.py`
  (`align_point_sets_kabsch`, `RigidPointSet.fit_pose`) and `coordinate_frame_ops.py`
  (`rotation_between_vectors` shortest-arc, `default_perpendicular`).
- `skeleton/components/segment_basis_solver.py` — `calculate_bases_for_segments`, the batched
  Gram-Schmidt basis solve grouped by axis convention.
- `skeleton/pose/` — the solve proper: `hydration.py`, `roll_resolution.py`,
  `segment_length_estimation.py`.

## The solve (one frame, no damping, no iteration)

1. **Hydrate each segment** (`hydrate_segment`):
   - **Rigid fit** when the segment is fully specified and ≥3 landmarks are observed: closed-form
     Kabsch (`MINIMUM_POINTS_FOR_RIGID_FIT = 3`; reflections and collinear sets are rejected).
     Roll is *measured* — these poses pass through roll resolution untouched.
   - **Direction fit** otherwise: shortest-arc rotation taking the origin→primary-direction ray
     onto its observed ray. Roll is not observable this way.
   - Fail-loud: `MissingLandmarkObservations` / `DegenerateObservations` — nothing repairs or guesses.
2. **Skip what cannot be solved:** `hydrate_skeleton(..., require_all=False)` returns a
   `SkeletonPose` holding only the segments that hydrated (occlusion is data). Callers tolerate
   missing segments; there is no hardcoded fallback direction.
3. **Resolve roll** (`ContinuousRollResolver.resolve_pose`): parallel-transport each
   direction-only segment's basis from the previous frame within the take (stateful per take;
   `reset()` for a new take; seeded from the rest pose at start). Output poses are tagged
   `PoseSolution.TRANSPORTED_ROLL`.
4. **Read the result:** `SegmentPose(origin, orientation, solved_by, has_resolved_roll)` inside a
   frozen `SkeletonPose` (`PoseSolution = {RIGID_FIT | DIRECTION | TRANSPORTED_ROLL}`). Local
   rotations compose as `q_local = conj(q_parent) · q_world`; freemocap falls back to world when
   the parent segment did not hydrate this frame.

## Coordinate systems in/out

Everything above runs in the canonical Blender convention
([../00-foundation/conventions.md](../00-foundation/conventions.md)). Other conventions
(VRM/glTF, ROS, ISB, Unreal, Unity) are declared in
`definitions/coordinate_systems/coordinate_systems.yaml` and entered/left ONLY at I/O boundaries
through `CoordinateSystemTransform` — never mid-pipeline.

## Design rules

- Entities carry pure accessors; anything that solves/mutates is a free function taking explicit
  inputs. One deliberate exception: `ContinuousRollResolver` carries per-take state, because roll
  continuity is inherently temporal.
- Hot path: batched solves, dict-backed indices built once at load, no per-frame allocations beyond
  necessity.
- Keyword-only arguments throughout; beartype validates every annotation.
