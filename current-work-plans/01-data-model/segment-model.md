# The Segment Model (the standard human in YAML + code)

**Describes:** how the standard human is authored, loaded, and held in memory —
`SkeletonDefinition` + the component YAMLs. The rest-pose authoring lives in
[reference-geometry.md](reference-geometry.md); the solve lives in
[../02-pipeline/kinematics-engine.md](../02-pipeline/kinematics-engine.md); vocabulary in
[../00-foundation/glossary.md](../00-foundation/glossary.md).

## The counts (canonical — link, don't restate)

The shipped standard human (`SkeletonDefinition.from_default_yaml()`) loads **61 segments /
124 landmarks / 60 joints / 5 chains**, declared across seven components. The linkage and chain
layers are built — `joints:` is the authoritative topology, `chains:` declares the spine + both
arms + both legs (see [linkage-chain.md](../05-linkage-chain/linkage-chain-design.md)). 52 ARKit
face blendshapes exist as a separate `FaceBlendShapes` object — not a skeleton component — and the
face component is commented out of the composition pending implementation.

## Composition

`definitions/human_skeleton/human_skeleton.yaml` is a composer, not content:

```yaml
name: human
coordinate_system: blender          # the canonical convention - see ../00-foundation/conventions.md
components:
  pelvis: { $include: components/pelvis.yaml }
  spine:  { $include: components/spine.yaml }   # sacrolumbar + thoracic + cervical_spine + clavicle
  skull:  { $include: components/skull.yaml }
  arm:    { $include: components/arm.yaml }
  hand:   { $include: components/hand.yaml }
  leg:    { $include: components/leg.yaml }
  foot:   { $include: components/foot.yaml }
#  face: { $include: components/face.yaml } #TODO - implement this
```

A `$include` resolves relative to the including file; duplicate names across components fail the
load. There is no `axial` part and no `head` segment — the spine owns `clavicle`/`thoracic`, the
skull is its own component.

## Component authoring format (real example — `components/leg.yaml`)

```yaml
sided: true                # file level: authored for the LEFT side; loader emits left_* + right_*

segments:
  UPPER_LEG:
    aliases: [femur]
    reference_geometry:
      origin: hip_joint
      z_axis:
        landmark: knee
        type: exact        # exact = measured every frame; approximate = Gram-Schmidt hint

landmarks:
  KNEE:
    aliases: [tibiofemoral_joint]
    definition: "Geometric center of the knee joint, between the femoral condyles and the tibial plateau"
    reference_frame: upper_leg      # explicit ownership - never "whoever declares it first"
    local_position: [0, 0, 0.267]   # body-height proportions, in the OWNING segment's local frame
```

Rules the loader enforces while building objects:

1. **`$include` resolution → lowercasing → sided expansion → reference-frame building → object
   wiring.** Authored names are UPPER_SNAKE; everything compiles to canonical lowercase.
2. **Sidedness:** `sided: true` instantiates `left_*` + `right_*`; the right side mirrors by
   **negating x-axis declarations** so both sides get local `+x` toward subject-right — see
   [../00-foundation/conventions.md](../00-foundation/conventions.md) for why it is an x-mirror.
3. **Ownership:** every landmark names its `reference_frame` segment; a segment's own origin
   landmark sits at `[0, 0, 0]` (enforced).
4. **References are objects, not strings** after load; a typo fails at the offending line.
5. **Aliases resolve once at load** via the `LandmarkNameResolver`; unknown aliases fail.

## What loads (per component)

| Component | Segments (per side where sided) |
|---|---|
| pelvis | pelvis (fully specified) |
| spine | sacrolumbar, thoracic (fully specified), cervical_spine + clavicle/sternoclavicular/acromion landmarks |
| skull | skull (fully specified) |
| arm | upper_arm, lower_arm ×2 |
| hand | carpals + thumb/index/middle/ring/pinky metacarpals + proximal/middle/distal phalanges ×2 (20/side) |
| leg | upper_leg, lower_leg ×2 |
| foot | foot, toes, heel ×2 (heel hangs off lower_leg at the ankle) |

Hand and finger chains are fully modeled (metacarpals included). Tracker *mappings* currently
cover only detector-emittable points — unmapped distal segments ride partial hydration / transport,
which is the articulated-model contract, not a modeling gap.

## Joints & chains (layers 5–6)

The linkage and chain layers are built: `joints:` in `human_skeleton.yaml` is the authoritative
topology (bilateral joints authored once via `sided: true`), and `chains:` declares the spine,
both arms, and both legs. `rest_pose.yaml` keeps only per-segment rest orientations; the parent
tree and `connect_at` live with the joints. See
[../05-linkage-chain/linkage-chain-design.md](../05-linkage-chain/linkage-chain-design.md).

## Loading in code

- `SkeletonDefinition.from_default_yaml()` — the shipped standard human.
- `SkeletonDefinition.from_yaml(path=...)` / `from_component_yaml(path=..., name=...)` — any model
  or single component (this is the extensibility seam the calibration-board rebuild will use).
- Global checks run once at load: unique names/aliases, one owning segment per landmark, every
  frame-definition point exists, no orphaned owners.
