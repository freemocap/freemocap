# Kinematics Engine

**Describes:** `skellyforge/kinematics/` — the math kernel that solves segment poses from landmarks.

## What this covers

Hydrated landmarks → per-segment world + local quaternions, `identity == T-pose`. The math kernel
(verified in the 2026-08-14 audit): `R = liveᵀ·ref`, Gram-Schmidt frame build, Kabsch/Umeyama (det=+1),
classical MDS for rigid templates.

## The solve (new ontology)

- **3+ landmarks (full rigid body)** — solve the rotation by **Kabsch** over the whole landmark cloud
  (reference rest positions → live positions). The head is the 7-point skull rigid body; hips, feet, toes
  are likewise full rigid bodies.
- **2 landmarks (simple)** — swing + damped minimal roll (the primary direction + the critically-damped filter).
- **linkage / chain** — a linkage computes the joint angle `conj(q_parent)·q_child`; a chain is the IK /
  FABRIK unit (future).

## Status

The new ontology classes are landed; `solve_frame_orientations` (the old swing+twist solver) is being
ported onto `RigidBodySegment` / `AnatomicalLandmark`, with the Kabsch path for 3+ landmark segments.
