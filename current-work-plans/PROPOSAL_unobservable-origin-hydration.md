# Proposal — hydrating the structurally-unobservable segment origins

**Status: pelvis LANDED (2026-08-19); hands resolved by the rigidifier rework; foot deferred.**
Signed off by jon. See "Outcome" per section.
**Decision it implements:** AUDIT §8.2 — *"Build mappings for the unobservable origins.
Hydrate `hand_trapezoid` / `hand_capitate` / `hand_hamate` (and the tarsals, and
`lumbosacral_junction`) from the keypoints the tracker does emit."*

> **What changed the scope:** `skeleton_rigidifier.py` was reworked to fit multi-point rigid bodies
> (3+ landmarks) by Procrustes **first**, off the raw hydrated landmarks, so a rigid body's *derived*
> landmarks (carpals, knuckles) are correct before anything hangs off them. That makes the **hand
> carpus** self-correcting (7 observed points: wrist + trapezium + 5 MCPs → the deep carpals ride the
> fit). Only the **pelvis** remains genuinely unfittable (3 *collinear* observed points), so §8.2's real
> job is the pelvis — done below.

## The problem, precisely

Many non-root **segment origins** are landmarks no tracker mapping produces. Today the
rigidifier fabricates them from their parent along the T-pose rest direction (fixed in Phase 1,
so they no longer shoot off sideways — but a fabricated origin is an *extrapolation*, not a
measurement). Two consequences worth removing:

1. **The pelvis root is degenerate every frame.** Only `hips_center`, `left_hip`, `right_hip`
   are hydrated, and `hips_center` is the midpoint of the other two — three **collinear** points.
   The Kabsch fit can't recover pelvic tilt/roll (Phase 3 now *detects* this and degrades to
   swing+twist; this proposal *removes* the degeneracy).
2. **The carpals/tarsals/5th-ray bases are pure extrapolation.** Anchoring metacarpal/metatarsal
   linkages on fabricated points means the whole hand/foot rides one rigid guess.

**Principle (from the ontology):** *observation-first — direct/FK where measured, IK/constraint
only where not.* So: hydrate every origin we reasonably can from real keypoints; let only the
genuinely-hidden ride the rigid solve.

## Mechanism: `anatomical_offset` (already in the mapping engine)

An `anatomical_offset` builds a local frame from keypoints and places a landmark at a
subject-scaled offset along that frame. **All offsets are ratios of a `reference_length`** (never
mm constants), so they scale with the subject. Ratios below are chosen to reproduce each
landmark's authored `local_position` at the T-pose, so `identity == T-pose` is preserved.

---

## 1. Pelvis — make the root a real 3D rigid body  *(highest value)*

Rest geometry (`pelvis.yaml`, pelvis frame `+X`=right, `+Y`=up, `+Z`=posterior; hips at `±88`,
so `hip_width W = 176`):

| landmark | rest_position | currently | proposed |
|---|---|---|---|
| `hips_center` | `[0,0,0]` | mean(hips) | unchanged |
| `left_hip`/`right_hip` | `[∓88,0,0]` | direct | unchanged |
| `lumbosacral_junction` | `[0,120,0]` | **fabricated** | offset: `up = 120/176 = 0.68 W` |
| `left_iliac_crest` | `[-88,80,0]` | **fabricated** | offset from `left_hip`: `up = 80/176 = 0.45 W` |
| `right_iliac_crest` | `[88,80,0]` | **fabricated** | offset from `right_hip`: `up = 0.45 W` |
| `pubic_symphysis` | `[0,-40,0]` | **fabricated** | offset: `up = -40/176 = -0.23 W` |

Frame for the offsets: `up = hips_center → neck_center` (trunk vertical), `lateral = left_hip →
right_hip`, `reference_length = hip_width`.

**Minimum to fix degeneracy:** just `lumbosacral_junction` (adds an off-hip-axis point → the fit
becomes planar rank-2, which Kabsch resolves). The iliac crests + pubis add robustness.

**Honest limitation:** with only the hips observed, the pelvis's *up* axis is borrowed from the
trunk vertical — so the pelvis can't tilt independently of the lower trunk. That's a sensible,
stable approximation (far better than a collinear garbage roll) and matches how markerless pelvis
is normally reconstructed. Flagging it explicitly.

---

## 2. Hand carpals + 5th-metacarpal base

Available keypoints: `wrist` (from the body pose), `trapezium` (`thumb_cmc`, already mapped), and
all five MCP joints. The deep carpals sit **between the wrist and the MCPs**, proximal.

| landmark (origin of…) | currently | proposed |
|---|---|---|
| `hand_trapezium` (thumb MC) | direct (`thumb_cmc`) | unchanged |
| `hand_trapezoid` (index MC) | fabricated | blend `wrist ↔ index_MCP`, proximal-biased |
| `hand_capitate` (middle MC) | fabricated | blend `wrist ↔ middle_MCP`, proximal-biased |
| `hand_hamate` (ring MC) | fabricated | blend `wrist ↔ ring_MCP`, proximal-biased |
| `hand_fifth_metacarpal_base` (pinky MC) | fabricated *(new in Phase 2)* | blend `wrist ↔ pinky_MCP`, proximal + ulnar |

**Form:** a weighted mean `{wrist: w, <finger>_MCP: 1-w}` is the simplest honest model (each carpal
lies ~on the wrist→MCP line); `w` per bone tuned to reproduce the rest positions. A small
palmar/dorsal (`z`) term needs `anatomical_offset` instead — **open question:** worth it, or is the
on-line blend enough for the carpus fit? (I lean: blend is enough; the carpus rigid-fits from 14
points regardless.)

The other carpals (`scaphoid`, `lunate`, `triquetrum`, `pisiform`) are **not** origins of anything —
they only pad the carpus Kabsch cloud. Leave them riding the solve (no mapping needed).

---

## 3. Foot tarsals + 5th-metatarsal base

Available keypoints differ by tracker — **this is the real constraint:**
- **MediaPipe:** `ankle`, `heel`, and **one** `foot_index` (both toes collapsed to a point).
- **RTMPose (wholebody):** `ankle`, `heel`, `big_toe`, `small_toe` — richer.

| landmark | currently | proposed |
|---|---|---|
| `foot_calcaneus` | direct (`heel`) ✓ | unchanged |
| `foot_talus` | fabricated | ≈ `ankle` (talus ≈ ankle joint center) |
| `foot_navicular`/`cuboid`/cuneiforms | fabricated | blend `ankle ↔ toe`, ~mid-tarsus, medial/lateral per bone |
| `foot_fifth_metatarsal_base` (5th MT) | fabricated *(new in Phase 2)* | blend `ankle ↔ toe`, lateral |

The forefoot fan (Phase 2) means the cuneiforms/cuboid have distinct medial/lateral offsets;
under MediaPipe's single toe point the lateral spread is estimated from the `ankle→heel→toe`
frame. **Open question:** author one mapping that works for both, or tracker-specific tarsal
mappings where RTMPose's extra toe point buys real lateral signal?

---

## 4. Vocabulary — `exact` / `approximate` in the offset frames  (AUDIT §8.1)

The `anatomical_offset` frames still use `kind: exact` / `kind: approximate` (e.g.
`mediapipe_body_…mapping.yaml`), which the ontology retired for segments in favour of
primary/twist. **My read:** this is a *different* concept — the *mapping's own* frame-construction
recipe (a Gram-Schmidt seed + hint for building the offset frame), not a segment frame — so the
words are defensible, but the collision deserves a one-line glossary note. **Confirm** (a) keep the
words with a glossary note, or (b) rename to `primary`/`twist` here too for one vocabulary.

## Outcome (2026-08-19)

1. **Pelvis — DONE.** `lumbosacral_junction` + both iliac crests + `pubic_symphysis` authored as
   `anatomical_offset` in **both** body mappings (`mediapipe_body_…` + `rtmpose_body_…`). Verified:
   each lands on its `pelvis.yaml` rest position at the T-pose (`test_pelvis_hydration.py`), and the
   hydrated cloud's 2nd singular value is a healthy fraction of the 1st (non-degenerate). The root now
   Kabsch-fits instead of degrading to swing+twist.
2. **Hand carpals — NOT NEEDED.** The Procrustes-first rigidifier rework derives the deep carpals from
   the carpus's 7 observed points. No carpal mappings authored (they would be redundant, and the on-line
   blend couldn't reproduce the off-line carpals exactly anyway). The hands solve correctly today.
3. **Foot tarsals — DEFERRED (tracker-limited).** The tarsus has only `ankle` + `heel` observed under
   MediaPipe (one collapsed toe point), so a shared hydration buys only foot *pitch*, not *roll*;
   RTMPose's `big_toe` + `small_toe` would buy roll, but tracker-specific foot mappings break the
   "every tracker produces the full set" boundary. The foot rides the (now correct) rest-forward
   fallback — an acceptable default for a secondary segment. Revisit if foot orientation becomes a
   requirement, driven by the RTMPose toe pair.
4. **§8.1 vocabulary — RESOLVED.** Kept `exact`/`approximate` for the mapping's construction frame; added
   a glossary note distinguishing it from a segment's primary/twist (`00-foundation/glossary.md`).
