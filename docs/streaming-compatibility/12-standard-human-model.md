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
clavicle base) can't be a convex mapping — that needs a **deferred** richer form (below).

Arm chain (worked example): `thorax → SC joint (clavicle base) → clavicle → GH joint (shoulder) → upperArm
→ elbow → lowerArm → wrist → hand`.

### Derived joint centers and the clavicle

# TODO NOTE - DO NOT DEFERR  A CORRECT FIX FOR THE STERNUM/SHOULDER offset!!! FIX IT CORRECTLY!!! WE NEED TO DO THIS CORRECTLY NOW DO NOT DEFER

- **Sternoclavicular (SC) joint = the clavicle base.** Anatomically the clavicle attaches at the
  **front-center of the upper chest** (manubrium), **not** the shoulder midpoint. The shoulder midpoint ≈
  **C7/T1** (the neck-bone base); the true SC joint is **anterior + slightly inferior** to it.
  **The honest anterior fix is deferred** — it can't be a convex mapping (string/list/dict all stay within
  the keypoints' hull, never anterior), so it needs a
  [richer mapping form that is explicitly deferred](13-tracker-to-canonical-mapping.md#deferred-richer-mapping-forms-later).
  **For v1**, the clavicle base uses the best convex mapping available (≈ `neck_center`) — a known
  approximation; the anterior correction lands when richer mappings do, **or** as a fixed anterior rest-offset
  baked into the clavicle bone's T-pose geometry (a rig-level offset, not a per-frame landmark).
- **Glenohumeral (GH) joint = upper-arm base.** Slightly inferomedial to the acromion "shoulder" keypoint —
  same story, a small offset, deferred with the SC fix.

**Scope:** `[IN]` for v1 — keep clavicle/shoulder on convex mappings, accept + note the approximation.
`[LATER]` — the anterior SC/GH correction, via richer mappings ([13](13-tracker-to-canonical-mapping.md)) or a
rig rest-offset.

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

## Open questions

- **Face blendshapes**: how driven from tracked face landmarks → VRM expression weights. `TBD`.
- **Anthropometric offset magnitudes** (SC/GH/hip) — starting values + whether the fit ritual refines them.
  `TBD`. # TODO NOTE - USE ANTHROPOMETRY TABLES AND REASONABLE GUESSES BASED ON SEGMENT LEENGTHS AND ANTHROPMETRY _ DO NOT TRY TO FIT 
- **Exact VRM bone subset** we target first (full humanoid vs. body+hands, face later). `TBD`. #TODO NOTE - FULL BODY, HANDS, and FACE - leave blendshapes as null values to start if we cant get them out of the SkellyTracker face tracker stuff we already do 
- **Scapula**: modeled (scapulothoracic rhythm) or folded into the clavicle/shoulder approximation? Leaning
  folded-in for v1. `TBD`. #TODO NOTE - Base on the clavbicale offset solution - we can add hte scaula stuff leter 
