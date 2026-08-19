# Kinematics Engine

**Describes:** `skellyforge/kinematics/` — the math kernel that solves segment poses from landmarks.

## What this covers

Hydrated landmarks → per-segment world + local quaternions, `identity == T-pose`. The math kernel:
Gram-Schmidt frame build, Kabsch/Umeyama (det=+1), `rotation_between_vectors` (swing), the
critically-damped filter, and rotation-pinned Procrustes for the rigid-fit.

## The solve (new ontology)

- **3+ landmarks (full rigid body)** — solve the rotation by **Kabsch** over the whole landmark cloud
  (reference rest positions → live positions): the skull (7 points), pelvis (7), hand carpus (14), foot
  tarsus (13), chest (4), and each thigh / shin (5).
- **2 landmarks (simple)** — swing + damped minimal roll (the primary direction + the critically-damped
  filter): the spine, neck, clavicle, upper/lower arm, and every metacarpal / phalanx / metatarsal /
  toe-phalanx.
- **linkage / chain** — a linkage computes the joint angle `conj(q_parent)·q_child`; a chain is the IK /
  FABRIK unit (future).

## Status

The solve is landed: `solve_frame_orientations` takes `HumanSkeleton` + `StandardHumanTPose` + hydrated
landmarks and returns `(FrameOrientationResult, SolveState)` (Kabsch for 3+ landmarks, swing+twist for 2).
