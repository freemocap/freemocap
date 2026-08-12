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
| `forward_axis` | +X, +Y, +Z (± sign) | Which axis the space treats as "forward". |
| `rotation_frame` | local, world | Are segment rotations relative to the parent segment (local) or to the world? **Under revision** — the stream now ships *both* frames as distinct channel groups, so a single value can no longer describe it. See [FMC-SR §2](phase-1/07-spec-reconciliation.md#2-channel-groups--resolve-the-09-vs-03-conflict). |
| `rotation_form` | quaternion, euler | And in what encoding (+ euler order if applicable). |

## The FreeMoCap canonical convention

**`millimeters · right-handed · +Z up · +X forward`** — robotics/biomechanics standards. Quaternions are
`wxyz`, identity == T-pose.

This is a **declared internal standard, not a derived observation.** All FreeMoCap data is in this
convention internally, always. It is an invariant every downstream consumer may rely on: the viewport, the
CoM calculation, the orientation solver, the standard stream, the exporters.

Two consequences that follow, and they are the whole reason this doc exists:

1. **Conversion happens at the edge, on request.** Foreign targets (VMC is Y-up/Z-forward/left-handed;
   Unreal is Z-up/X-forward/left-handed/cm) are reached by the
   [one conversion function](#one-conversion-function), invoked by the adapter that declares that target.
   Nothing converts in the middle, and nothing converts implicitly.
2. **Re-orientation is an explicit user action.** If a user wants the world moved — to make a recording
   line up more nicely, to match a room, to match another system — that is a **deliberate re-orientation
   requested through the HTTP control plane** ([04](04-http-control-plane.md)), applied to the world
   transform, and **declared in the schema**. It is never a silent adjustment somewhere in the pipeline.

### Where the world transform comes from

The convention says what the axes *mean*. The **calibration** is what puts the data into them, and it
defines the world frame in one of these ways:

| Method | What it sets | Notes |
|---|---|---|
| **Charuco ground plane** | Board plane becomes `z = 0`; board origin becomes the world origin; the in-plane rotation follows the board's orientation on the floor. | `estimate_board_groundplane()` Kabsch-fits the board, then `orient_up_toward_cameras()` orients `+Z` toward the camera centroid (cameras sit above the floor) and re-derives `Y = Z × X` to keep the basis right-handed. **That the in-plane rotation depends on how the board was laid is expected and fine** — we give users guidance on board placement for best compatibility, but variation is acceptable. |
| **Camera 0 pinned to origin** | Used when ground-plane alignment is not run. World frame = camera 0's frame. | `pin_camera_0_to_origin` (anipose) / `pin_camera_0` (pyceres). |
| **User offset** `[LATER]` | A user-supplied transform applied on top, via the HTTP control plane. | See consequence 2 above. |

**The world transform FreeMoCap produces is authoritative and is carried through the wire unmodified.**
The stream never silently re-orients data; it declares the convention and ships what the pipeline made.

> **Invariant to verify, not assume.** Since `+Z up / +X forward` is a *standard the data must satisfy*, any
> calibration path that leaves the world in some other orientation is a defect in that path — not a reason
> to weaken the schema. The camera-0-pinned path is the one to check: an optical camera frame is not
> Z-up, so either it is re-oriented into the canonical convention before data flows, or it violates the
> invariant. Tracked as **D35** in [FMC-SR](phase-1/07-spec-reconciliation.md#10-defect-register--everything-found-nothing-deferred).

### Subject-relative constructions

Anatomical frames built from the subject's own landmarks do not depend on the world's in-plane orientation
at all, and are correct under any of the world-definition methods above. The `anatomical_offset` form
([13](13-tracker-to-canonical-mapping.md#richer-mapping-form-anatomical_offset-local-basis-offset-in)) is
the case that matters: with `up = hips_center → neck_center` (exact) and
`lateral = left_shoulder → right_shoulder` (approximate), `anterior = up × lateral` recovers true anterior.

Verified numerically at five arbitrary subject facings (0°, 37°, 90°, 180°, 265° in the ground plane):
`up × lateral` reproduced the true facing direction exactly in every case, so the sternoclavicular offset is
anterior, not posterior. **This holds because the basis is right-handed** — the handedness guarantee is
load-bearing for anatomy, not only for rendering.

### Rotations

Rotations are produced by the folded-in kinematics engine ([11](11-kinematics-fold-in.md)) in **both**
world and parent-relative frames, shipped as two channel groups. The direction convention of the world
quaternion — and the parent-relative composition that follows from it — is specified in
[§ Segment rotation conventions](#segment-rotation-conventions) below.

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
| **FreeMoCap (source / standard stream)** | right | +Z (**forward +X**) | mm | quaternion `wxyz`, identity == T-pose |
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

## Segment rotation conventions

Two facts that were previously inferable only from docstrings, and are stated here because every consumer
of `ROTATIONS_WORLD` / `ROTATIONS_LOCAL` depends on them.

**Component order is `wxyz`.** Identity — and therefore the T-pose, per
[01](01-canonical-data-model.md#the-rest-pose--t-pose-reference) — is `(1, 0, 0, 0)`. Any doc, test, or
fixture printing a literal quaternion must name its order; Three.js and Unity use `xyzw` and the swap is
silent.

**Direction: a world quaternion maps segment-frame → world.** `q_world` takes a vector expressed in the
segment's own T-pose frame and expresses it in the canonical world frame. Equivalently: `q_world` is the
rotation carrying the segment *from* its declared rest orientation *to* its current one, which is exactly
the `identity == T-pose` contract.

**The composition that follows.** With Hamilton product semantics `R(q₁ · q₂) = R(q₁) ∘ R(q₂)` (apply `q₂`
first):

```
q_child_world = q_parent_world · q_child_local
        ⟹  q_child_local = conj(q_parent_world) · q_child_world
```

The operand order is not cosmetic — quaternion multiplication does not commute, and the reversed form
`q_child_world · conj(q_parent_world)` yields a rotation of the correct *angle* about the wrong *axis*: the
delta expressed in the world frame rather than relative to the parent. Since `ROTATIONS_LOCAL` is what
VMC and Unreal consume, that error surfaces as [the local-rotation trap](#the-local-rotation-trap-vmc-and-unreal)
below.

> **Testing note.** A uniform bend — every segment rotated identically — cannot distinguish the two
> orderings, because `q_child == q_parent` makes both reduce to identity. Any test pinning this convention
> must use a **differential** case (parent and child rotated by different amounts about different axes) plus
> a `recompose(parent, local) == child` round-trip. Specified in
> [14 — Engine Testing Strategy](14-engine-testing-strategy.md).

## Why a self-written receiver can't validate this

A receiver you wrote yourself shares your misconceptions: flip handedness in both your adapter
and your test viewer and everything looks perfect while a real third-party consumer explodes.
Convention correctness is therefore validated by **golden vectors** plus **at least one real
third-party consumer** per protocol — see [08 — Testing Strategy](08-testing-strategy.md).
