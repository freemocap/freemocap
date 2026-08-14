# Glossary

The vocabulary shared across every layer. **Keypoint** and **segment** are the only two nouns for the
data; "landmark" and "canonical" (as a mapping layer) are **retired**.

## Data

- **keypoint** — a point tracked in 2D and triangulated to 3D, named by the tracker. May be **derived**
  (a mean of others, or an `anatomical_offset` from a tracked point — e.g. `head_vertex`, `foot_ball`,
  `jaw`). Produced by **skellytracker**; the mapping renames/derives tracker points into the names the
  segment model declares.
- **segment** — a VRM-1.0-aligned **rigid body**: an **origin**, an **orientation**, and a **length**.
  Owned by **skellyforge**. *Not* an anatomical bone — `HumanBone` names are VRM's vocabulary. The model
  is **60 segments**; their union of keypoints is the **76** a tracker must supply.
- **rigid_points** — the explicit set of keypoints rigid on a segment (fixed pairwise distances). Two
  points → a single axis (the degenerate rigid body); 3+ → the full rigid-body fit.
- **origin_keypoint** — the segment's origin; every axis direction starts here. Must be in `rigid_points`.

## Frame construction

- **axis (declaration)** — one of a segment's tagged local-frame axes: a **name** (`x`/`y`/`z`, which
  basis vector it defines), a **kind**, and a **`target_keypoint`** (in `rigid_points`). Its direction is
  `positions[target_keypoint] − positions[origin_keypoint]` — the segment's own geometry only.
  - **EXACT** — the segment's defining direction, resolved directly every frame.
  - **APPROXIMATE** — a soft direction reference for a second basis axis, Gram-Schmidt'd against the
    exact axis; when absent, the segment's roll falls to the damped minimal-roll tier.
- **reference geometry** — the T-pose each live pose is measured against (`identity == T-pose`).
- **standard human** — the composed 60-segment model (body midline + limbs ×2 + hands ×2 + face).

## Twist tiers (a *consequence* of the declaration, not a separate policy)

1. **Resolved** — an APPROXIMATE axis is declared and usable this frame → the roll resolves from the
   segment's own geometry.
2. **Damped-minimal** — otherwise → swing-only, roll carried by the critically-damped filter.

> The **linkage/chain layer** (resolving an under-determined segment's twist from its neighbours) is
> **future work** — do not describe it as current. Twist today is own-geometry-or-damped.

## Retired (do not reintroduce outside `archive/`)
`landmark`, `canonical` (mapping sense), `long_axis_keypoint`/`twist_keypoint`, `from_keypoint`/
`to_keypoint`. (MediaPipe's own `PoseLandmarker` *product* name is the sole exception.)
