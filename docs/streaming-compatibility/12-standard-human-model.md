# 12 — Standard Human Model

> The canonical "standard human": a **VMC/VRM-aligned humanoid rig** carried alongside the anatomical
> markers (the LSL + VMC blend). It defines what the schema describes and what every avatar adapter
> retargets from. Owned by **SkellyModels** (in SkellyForge); the FreeMoCap realtime pipeline consumes it
> via a per-frame variant.
>
> Status: **design, partly confirmed.** Decisions marked; open items are `TBD`.

## Decisions (confirmed)

- **Human shape = the VMC/VRM humanoid**: full body + hands + face (blendshapes). One standard.
- **Rigid-body-per-bone**: each VRM bone is a rigid body (a rest-pose reference geometry + an orientation),
  animated by the copied-in kinematics engine ([11](11-kinematics-fold-in.md)).
- **Superset (LSL + VMC)**: the model carries **both** the measured anatomical markers (points +
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
one abstraction; there are **no "virtual markers."** Some endpoints are direct keypoints; some are **derived**
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

## Per-bone twist policy (the underdetermined-roll plan)

A 2-joint bone gives position + long-axis **swing** (determined) but leaves **twist/roll** free. Resolve per
bone, best-available first:

1. **Full frame** — ≥3 non-collinear markers → full orientation directly (Kabsch): head, pelvis, thorax,
   hands, feet.
2. **Swing + chain-resolved twist** — the child/hinge direction supplies the roll reference, because elbows
   and knees are 1-DOF hinges: `upperArm` twist ← elbow-hinge (forearm dir); `lowerArm` twist ← hand frame;
   `upperLeg` twist ← knee (shank dir); `lowerLeg` twist ← foot frame.
3. **Swing + damped minimal twist (fallback)** — when the twist source is occluded, hold zero/rest twist and
   **temporally damp** it (critically-damped) to avoid jitter/pop. (This is the "damped-track roll-minimizing"
   default.)

Fits the engine's frame model directly: the `CoordinateFrameDefinition`'s **exact axis** = the bone long axis;
its **approximate axis** = the twist source (on-bone markers → child/hinge → none/minimal). Per bone we
declare the **axis-source policy**; the math is unchanged.

## Rest pose (T-pose)

The canonical human ships a declared T-pose: rest positions for every joint (incl. derived centers) and,
per bone, a reference orientation such that **identity rotation == T-pose**. This is the schema's rest-pose
reference ([01](01-canonical-data-model.md#the-rest-pose--t-pose-reference)) and the disk reference geometry
([10](10-serialization-and-tidy-format.md)).

## Honesty / confidence

Each bone's rotation declares which DOF were **observed / inferred / free**, and derived joint centers carry
lower confidence than directly-observed markers — surfaced on the stream's confidence channels
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
