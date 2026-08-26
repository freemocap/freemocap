# The Biomechanics Layer (derived quantities)

**Describes:** `skellyforge/core/biomechanics/` — mass, CoM, inertia, ground reference, derived
kinematics — and how freemocap streams the results. This layer reads the skeleton + pose layers and
is never imported by them (enforced by `test_no_cross_import.py`). Design record:
skellyforge's own `current-work-plans/biomechanics-revival-plan.md`.

## What lives there

| Module | Contents |
|---|---|
| `anthropometric_parameters.py` | de Leva (1996) segment inertial parameters: mass fractions, CoM fractions, sagittal/transverse/longitudinal radii of gyration; 10 anatomical segments (trunk split upper/middle/lower), bilaterals counted twice so fractions sum to 1. Authored in `anthropometric_parameters.yaml`. |
| `center_of_mass.py` | `CenterOfMassDefinitions`: each anatomical segment's CoM as a weighted sum of **landmarks** along a proximal→distal long axis (`center_of_mass.yaml`). Partial-CoM aware: occluded landmarks are skipped, so a segment CoM can exist from a subset. |
| `segment_mapping.py` | maps all 61 skeleton segments → 16 sided de Leva anatomical names; distributes body mass accordingly. |
| `segment_inertia.py` | per-segment inertia tensor (solid-cylinder model oriented on the long axis). |
| `composite_inertia.py` | whole-body CoM + inertia via the parallel-axis theorem (`BodyInertialProperties`). |
| `ground_reference.py` | CoP (from force/moment), XCoM = extrapolated CoM / Hof capture point, CMP; `GRAVITY_ACCELERATION` ships here. |
| `derived_kinematics.py` | CoM velocity/acceleration by central differences; rejects non-increasing timestamps. |

## What every skeleton gets, and what it opts into

**Every skeleton has a centre of mass.** With no declared mass distribution the default is the
**unweighted mean of a segment's landmarks** per segment, and of the segment CoMs for the whole
model. The human's `center_of_mass.yaml` weighted sums are an *override* of that default, not a
precondition for having one — which is why a charuco board gets a CoM for free without inventing a
board-specific path.

**Everything else is opt-in.** Inertia, XCoM, CoP, CMP and roll resolution need declarations the
model may not have (mass fractions, radii of gyration, roll conventions). A skeleton lists what it
wants in its `derived_quantities:` section, and asking for one whose inputs are undeclared **raises
at load, naming the missing declaration** — never a quiet zero. That list is also the place to attach
new derived quantities to a model without touching the ones that do not want them.

This is the [sensible-defaults principle](../00-foundation/conventions.md) applied to this layer: the
default is part of the specification, and what a default cannot answer fails loudly.

For the charuco board that means: a CoM, no inertia, no XCoM, no roll resolver.

## How freemocap consumes it (realtime)

In the aggregator, gated by `center_of_mass_enabled`:

1. Composition: load both default YAMLs; `com_definitions.validate_against(skeleton=...)` fails the
   run if a weighted landmark does not exist; per-segment masses = `mass_fraction × assumed 70 kg`.
2. Per frame: `landmark_world_positions(skeleton=..., pose=resolved_pose, segment_scales=...)` →
   `compute_segment_coms(definitions=..., world=...)` →
   `whole_body_center_of_mass(segment_coms=..., segment_masses=...)`.
3. XCoM: velocity by finite difference against the previous frame's CoM, then
   `extrapolated_center_of_mass(com=..., com_velocity=..., gravity=GRAVITY_ACCELERATION)`.
   State resets on calibration hot-reload.
4. Publish: `total_body_com` + `xcom` ride `AggregationNodeOutputMessage`; the
   `DerivedProducer` emits them as `DERIVED_POINTS` rows named `center_of_mass` / `xcom`.
   Frames where nothing hydrated carry no CoM (the block is skipped) — never zeros.

The centroidal-kinematics block (inertia → acceleration dynamics) is stubbed but commented out in
the aggregator pending a consumer.

## Rules

- Pure functions in, values out — no solver classes; state (previous CoM/time) belongs to callers.
- Every weighted definition is validated against the live skeleton at composition time; a renamed
  landmark fails fast, not silently at first use.
- Landmark world positions need the model's **scale**, because local positions are proportions of its
  reference unit. Without it every landmark collapses onto its segment origin and the CoM silently
  becomes a mass-weighted average of joint centres
  ([model-scale-fitting.md](model-scale-fitting.md)).
