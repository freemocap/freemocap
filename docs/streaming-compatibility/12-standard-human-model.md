# 12 — Standard Human Model

> The canonical "standard human": a **VMC/VRM-aligned humanoid rig** carried alongside the measured
> keypoints (the LSL + VMC blend). It defines what the schema describes and what every avatar adapter
> retargets from. Owned by **SkellyModels** (in SkellyForge); the FreeMoCap realtime pipeline consumes it
> via a per-frame variant.
>
> Terminology used throughout — *keypoint* / *landmark* / *segment* — is defined in
> [13](13-tracker-to-canonical-mapping.md#two-kinds-of-trajectory).
>
> Status: **design, partly confirmed.** Decisions marked; open items are `TBD`.

## Segments, not anatomical bones

**Scope note, and it governs everything below.** We are **not** currently modelling anatomical bones. We
fit **3D-oriented segments** matched to the **VRM 1.0** schema — the level of abstraction that avatar and
streaming formats (VMC, Unreal Live Link) operate at, and the level the 3JS mesh renderer
([phase-1/06](phase-1/06-rigid-body-bone-renderer.md)) draws.

A segment is a rigid body with a reference geometry, a set of attached landmarks, and an orientation. That
is all it claims to be. It does **not** claim to be a femur.

- Where the code says `HumanBone`, `human_bones.py`, `BONE_ALIASES`, `bone_names` — that is **VRM's
  vocabulary**, adopted so the alias table maps cleanly onto VRM and Unreal targets. It is not an
  anatomical assertion, and a reader should not infer anatomical precision from it.
- **Anatomically-aligned bone models are `[LATER]`.** When they arrive, segments become the layer anatomy
  attaches *to* — not the layer that gets replaced.
- This qualifies locked decision 3 in
  [phase-1/standard-human-model](phase-1/standard-human-model/README.md) ("bones subsume segments"). The
  *structural* claim stands — one rigid body per segment, each carrying its own reference geometry, no
  parallel `segment_connections` concept. The entities are VRM-aligned segments.

## Decisions (confirmed)

- **Human shape = the VMC/VRM humanoid**: full body + hands + face (blendshapes). One standard.
- **Rigid-body-per-bone**: each VRM bone is a rigid body (a rest-pose reference geometry + an orientation),
  animated by the copied-in kinematics engine ([11](11-kinematics-fold-in.md)).
- **Superset (LSL + VMC)**: the model carries **both** the measured keypoints and fitted landmarks (points +
  confidence/error, for research/LSL) **and** the rig (bones + rotations + blendshapes, for avatars).
- **SSOT in SkellyModels**; realtime pipeline uses a per-frame variant.

## The rig (VRM humanoid bone set)

Body: `hips` (root) → `spine` → `chest`/`upperChest` → `neck` → `head` (+ `eyes`, `jaw`).
Arms (×2): `shoulder` (clavicle) → `upperArm` → `lowerArm` → `hand`.
Legs (×2): `upperLeg` → `lowerLeg` → `foot` → `toes`.
Fingers (×2, optional): thumb/index/middle/ring/little × 3 phalanges.
Face: VRM **blendshapes** (expressions), not bones — `TBD` how driven (see Open questions).

## Marker → bone retarget

Each bone's endpoints are **joint centers**, produced from tracker keypoints via a
[tracker→canonical mapping](13-tracker-to-canonical-mapping.md) (string / list-mean / weighted-sum) — the
one abstraction. Some endpoints are direct keypoints; some are **derived**
landmarks (`neck_center`, `hips_center`, …). Joint centers that sit *off* the marked surface (the anterior
clavicle base) can't be a convex mapping — they use the **`anatomical_offset`** mapping form (below).

Arm chain (worked example): `thorax → SC joint (clavicle base) → clavicle → GH joint (shoulder) → upperArm
→ elbow → lowerArm → wrist → hand`.

### Derived joint centers and the clavicle

Solved **now** with the `anatomical_offset` mapping form ([13](13-tracker-to-canonical-mapping.md)) — a
deterministic, subject-scaled offset in a landmark-defined frame, **no runtime fitting**.

- **Sternoclavicular (SC) joint = the clavicle base.** The clavicle attaches at the **front-center of the
  upper chest** (manubrium), **not** the shoulder midpoint (≈ **C7/T1**, the neck-bone base) — the true SC
  joint is **anterior + slightly inferior**. Produce it via `anatomical_offset`: origin = shoulder midpoint; trunk
  frame (up = `hips_center→neck_center`, lateral = shoulder→shoulder, **anterior = up × lateral**); offset ≈
  15% shoulder-width anterior + a small inferior term (anthropometric ratios). Keep `neck_center` for the
  **neck** bone; the SC joint is a *separate* anterior landmark for the **clavicle** base — this replaces the
  "clavicle → neck_center" error.
- **Glenohumeral (GH) joint = upper-arm base.** Slightly inferomedial to the acromion "shoulder" keypoint —
  the same `anatomical_offset`, smaller magnitude.
- **Hip joint centers / pelvis / thorax origins** — same mechanism wherever an off-surface center is needed.

Offsets are **anthropometry-table ratios of segment lengths**, subject-scaled — **never runtime-fit**. The
identical definition places both the T-pose rest position and the live per-frame landmark.

## Per-segment twist policy (the underdetermined-roll plan)

A 2-joint segment gives position + long-axis **swing** (determined) but leaves **twist/roll** free. Resolve
per segment, best-available first:

1. **Full frame** — ≥3 non-collinear landmarks on the segment → full orientation directly (Kabsch): head, pelvis, thorax,
   hands, feet.
2. **Swing + chain-resolved twist** — the child/hinge direction supplies the roll reference, because elbows
   and knees are 1-DOF hinges: `upperArm` twist ← elbow-hinge (forearm dir); `lowerArm` twist ← hand frame;
   `upperLeg` twist ← knee (shank dir); `lowerLeg` twist ← foot frame.
3. **Swing + critically-damped minimal twist (fallback)** — when the twist source is occluded, hold
   zero/rest twist and damp it over time to avoid jitter and pop. Specified below.

Fits the engine's frame model directly: the `CoordinateFrameDefinition`'s **exact axis** = the segment long
axis; its **approximate axis** = the twist source (on-segment landmarks → child/hinge → none/minimal). Per
segment we declare the **axis-source policy**; the math is unchanged.

### Critical damping — specification

"Critically damped" is meant literally, and it is what tier 3 must implement. Written out because the term
was previously used loosely: the code is a **first-order exponential lag** (a per-frame blend weighting the
previous frame at 0.95), which is a different filter with different behaviour, and it is documented here as
critical damping. Tests in [14 § critical damping](14-engine-testing-strategy.md#5-critical-damping).

**The filter.** Second-order, critically damped — the fastest response that does not overshoot. Per segment,
carry an **angular-velocity state** across frames alongside the orientation, and integrate toward the target
with the damping ratio fixed at 1. A first-order lag cannot express this: it never overshoots, but it also
cannot settle quickly, so it trades pop for lag rather than removing both.

**The parameter is a time constant in seconds**, not a per-frame blend factor. This is the load-bearing
change. A blend factor silently means different things at 30, 60 and 120 fps — the same nominal "0.95"
gives a settling time that varies with framerate, so a rig tuned on one machine misbehaves on another. A
time constant is framerate-independent by construction; the per-frame coefficient is derived from it and
`dt`. `TwistPolicy.damping_factor` becomes a time constant field accordingly.

**Required behaviours:**

- **Damping applies on every fallback path.** When the twist source is occluded *or* the singularity gate
  trips, the damped-minimal solve must receive the previous frame's state. This is the case damping exists
  for; skipping it there produces exactly the pop the tier is meant to prevent. (The current code passes no
  previous state on both fallback paths — defect D3.)
- **First frame:** no previous state → return the current value undamped, and seed velocity at zero.
- **After a gap:** do not integrate stale velocity across it. Treat a discontinuity in time like a first
  frame rather than accelerating through the gap.
- **Reset clears the state.** Damping never carries across recordings or sessions.
- **State is owned by the solver instance**, not module scope — see defect D16.

## Rest pose (T-pose)

The canonical human ships a declared T-pose: rest positions for every joint (incl. derived centers) and,
per bone, a reference orientation such that **identity rotation == T-pose**. This is the schema's rest-pose
reference ([01](01-canonical-data-model.md#the-rest-pose--t-pose-reference)) and the disk reference geometry
([10](10-serialization-and-tidy-format.md)).

## Honesty / confidence

Each bone's rotation declares which DOF were **observed / inferred / free**, and derived joint centers carry
lower confidence than landmarks derived directly from observed keypoints — surfaced on the stream's confidence channels
([09](09-standard-stream-protocol.md)). Positive-definition style: we say what we measured, not what we didn't.

## Resolved / open

- **VRM bone subset (resolved):** target the **full body + hands + face** from the start. Face **blendshapes
  start as `null`** until we can derive them from the SkellyTracker face-tracking we already run.
- **Offset magnitudes (resolved):** from **anthropometry tables + reasonable ratios of segment lengths** —
  **do not runtime-fit** them.
- **Scapula (resolved → later):** built on the **same `anatomical_offset` mechanism** as the clavicle; add the
  scapulothoracic detail **`[LATER]`**, after the SC/GH offsets land.
- **Face blendshapes (open):** how tracked face landmarks drive VRM expression weights — `null` until wired.
  `TBD`.
