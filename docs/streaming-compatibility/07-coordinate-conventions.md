# 07 — Coordinate Conventions

> Every integration bug in this space is, eventually, a coordinate bug. The targets genuinely
> disagree about units, handedness, up-axis, and how rotations are expressed. This document
> makes convention a **first-class schema fact**, not a comment and not a per-frame payload.

## Convention is a schema fact

A coordinate convention is an explicit value declared **once, in the stream's schema**
([01 — schema + samples](01-canonical-data-model.md#the-stream-schema--samples)) — never
repeated per sample. Each protocol adapter declares its *target* convention the same way. It
is the tuple:

| Component | Values | Notes |
|---|---|---|
| `units` | mm, cm, m | Linear scale. |
| `handedness` | right, left | |
| `up_axis` | +X, +Y, +Z (± sign) | Which axis points "up". |
| `forward_axis` | +X, +Y, +Z (± sign) | Which axis the subject faces. |
| `rotation_frame` | local, world | Are bone rotations relative to the parent bone (local) or to the world? |
| `rotation_form` | quaternion, euler | And in what encoding (+ euler order if applicable). |

**FreeMoCap's canonical convention (robotics/biomechanics standards):** `millimeters,
right-handed, +Z up`, forward-axis `TBD` (trigger: confirm against the ground-plane calibration
basis — the calibration derives a right-handed basis and the Blender export path treats data as
X-right / Y-forward / Z-up). Rotations, once produced by the SkellyModels extension (see
[01](01-canonical-data-model.md)), are `TBD` local-vs-world at the source — but the hub
normalizes to a documented canonical choice, declared in the schema, before adapters see them.

## One conversion function

There is exactly **one** convention-conversion function in the hub. It takes
`(value, from_convention, to_convention)` and handles: unit scaling, axis remap / handedness
flip (a signed permutation of axes), and rotation-frame/-form conversion. Adapters never
hand-roll axis math — they call the converter with their declared target convention. This is a
[derived view](02-streaming-hub.md#derived-views): conversions are computed once per frame for
the union of active targets, not per-adapter.

The same-shape transports (UI over WebSocket, the LSL route) carry the **canonical** convention
unchanged — the receiver reads it from the schema. Only *foreign-protocol adapters* whose target
differs (VMC, Unreal, …) invoke the converter.

Rationale: hand-rolled flips scattered across adapters are how you get a viewer that looks
perfect while VSeeFace explodes. One converter, tested against golden vectors
([08](08-testing-strategy.md)), is the guard.

## Per-target convention table

Verified target conventions (from the VMC research prototype and protocol docs). `—` means the
protocol doesn't pin it / it's negotiated per rig.

| Target | Handedness | Up | Units | Rotation form |
|---|---|---|---|---|
| **FreeMoCap (source / standard stream)** | right | +Z | mm | quaternion (canonical) |
| VMC / Unity | left | +Y | m | quaternion, **local** |
| Rokoko | — | +Y (Z-fwd) | m | quaternion, world |
| VRChat OSC | — | +Y | m | **Euler angles** |
| Unreal Live Link | left | **+Z** | **cm** | quaternion, local |
| Qualisys RT | — | — | **mm** | quaternion |

The spread across this table — three different up-axes, three different unit scales, local vs.
world rotations, quaternion vs. Euler — is the entire justification for treating convention as a
declared schema value.

## The local-rotation trap (VMC and Unreal)

VMC bone rotations are **local to the parent** — the spec never says this plainly, and it is the
single most common VMC implementation bug (it produces a memorable explosion). The
canonical→VMC adapter must:

1. Convert handedness (right → left) and up-axis (+Z → +Y).
2. Express each bone's rotation **relative to its parent**, in the target rig's rest pose.
3. Guarantee **identity == T-pose** (see [01 — rest pose](01-canonical-data-model.md#the-rest-pose--t-pose-reference)).

This logic is a shared [derived view](02-streaming-hub.md#the-humanoid-retarget) (the humanoid
retarget), not per-adapter code — VMC, Rokoko, and Unreal all want "named bones with rotations
relative to a declared rest pose," so it is computed once.

## Why a self-written receiver can't validate this

A receiver you wrote yourself shares your misconceptions: flip handedness in both your adapter
and your test viewer and everything looks perfect while a real third-party consumer explodes.
Convention correctness is therefore validated by **golden vectors** plus **at least one real
third-party consumer** per protocol — see [08 — Testing Strategy](08-testing-strategy.md).
