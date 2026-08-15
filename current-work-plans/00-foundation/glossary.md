# Glossary

The vocabulary shared across every layer, grounded in [the ontology](../ontology.md). The data nouns are
**keypoint** (measured), **landmark** (segment-local named point), and **segment** (oriented volume).
"Canonical" as a *mapping layer* stays retired; **the term "landmark" is revived** with a precise meaning.

## Data (the ontology stack — see [ontology.md](../ontology.md))

- **keypoint** — a measured 3D world point, tracker-named. May be **derived** (a mean, or an
  `anatomical_offset` from a tracked point — e.g. `head_vertex`, `foot_ball`, `jaw`). Produced by
  **skellytracker**; pure measurement.
- **mapping** — the one seam: hydrates a landmark from keypoints (direct / weighted / offset). The
  skellytracker ↔ skellyforge interface.
- **landmark** — a **named point in a segment's local frame** (skellyforge). Two faces: a *static local
  definition* (rest shape) + a *per-frame world hydration* (or absent = occlusion). The atom of the model.
  *(The old vague "landmark **layer**" is retired; this precise sense is revived — standard biomech/rigging usage.)*
- **segment** — an **oriented volume of space**: origin + orientation (+ length), solved from its
  landmarks. VRM-1.0-aligned; *not* an anatomical bone (`HumanBone` is VRM's vocabulary). The model is
  **60 segments / 76 landmarks** (single-sourced here; composition per
  [01-data-model/segment-model.md](../01-data-model/segment-model.md)). 2 hydrated landmarks → simple
  (roll carried by the damped filter); 3+ non-collinear → full 6-DOF.
- **rigid child** — a segment authored `rigid_with_parent` whose landmarks are all members of its
  parent's landmark set: no independent solve, it inherits the parent's pose composed with its rest
  local rotation. Declared, never inferred. (The head's eye / ear / nose segments.)
- **skeleton** — the rooted parent→child tree of segments; a joint angle is the *derived* relative
  orientation, not a modeled constraint.

## Frame construction

- **axis (declaration)** — one of a segment's tagged local-frame axes: a **name** (`x`/`y`/`z`, which
  basis vector it defines), a **kind**, and a **`target_landmark`** (in the segment's `landmarks`). Its
  direction is `positions[target_landmark] − positions[origin_landmark]` — the segment's own geometry
  only.
  - **EXACT** — the segment's defining direction, resolved directly every frame.
  - **APPROXIMATE** — a soft direction reference for a second basis axis, Gram-Schmidt'd against the
    exact axis; when absent, the segment's roll falls to the damped minimal-roll tier.
- **reference geometry** — the T-pose each live pose is measured against (`identity == T-pose`).
- **standard human** — the composed 60-segment model (body midline + limbs ×2 + hands ×2 + face).

## Twist tiers (a *consequence* of the declaration, not a separate policy)

1. **Resolved** — an APPROXIMATE axis is declared and usable this frame → the roll resolves from the
   segment's own geometry.
2. **Damped-minimal** — otherwise → swing-only, roll carried by the critically-damped filter.

> The **linkage/chain (constraint/solve) layer** — resolving an under-determined segment's twist from its
> neighbours — is **future work** (see [ontology.md](../ontology.md)); do not describe it as current.
> Twist today is own-geometry-or-damped.

## Retired (do not reintroduce outside `archive/`)
The old **landmark *layer*** (a vague intermediate fitted-point stage) — but note **the *term* `landmark`
is revived** above with a precise meaning. Also retired: `canonical` (mapping sense),
`long_axis_keypoint`/`twist_keypoint`, `from_keypoint`/`to_keypoint`. (MediaPipe's own `PoseLandmarker`
*product* name is the sole exception.)
