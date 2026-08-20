# Proposal — hydrating the structurally-unobservable segment origins

**Status:** proposal, awaiting sign-off (jon). Nothing authored yet.
**Decision it implements:** AUDIT §8.2 — *"Build mappings for the unobservable origins.
Hydrate `hand_trapezoid` / `hand_capitate` / `hand_hamate` (and the tarsals, and
`lumbosacral_junction`) from the keypoints the tracker does emit."*

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
landmark's authored `rest_position` at the T-pose, so `identity == T-pose` is preserved.

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

## What I need from you

1. **Pelvis:** OK to author `lumbosacral_junction` + iliac crests + pubis as above? (or minimal:
   just `lumbosacral_junction`?)
2. **Carpals/tarsals:** OK with the on-line weighted-blend approach, or do you want the palmar/z
   term (full `anatomical_offset`) from the start?
3. **Foot / tracker split:** one shared tarsal mapping, or RTMPose-specific richer version?
4. **§8.1 vocabulary:** glossary note vs. rename.

Once you sign off, authoring is straightforward: add the entries to the four
`*_to_standard_human_mapping.yaml` files, verify each hydrated point lands on its rest position at
the T-pose (identity), and confirm the pelvis Kabsch is non-degenerate.
