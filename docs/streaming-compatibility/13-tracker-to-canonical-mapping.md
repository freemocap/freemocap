# 13 — Tracker → Canonical Landmark Mapping

> The boundary between **SkellyTracker** (which produces *keypoints*) and the **canonical human model**
> in **SkellyForge** (which is defined in *landmarks*). This mapping is the **single** abstraction for
> "how does a tracker's output become the standard human" — and it **replaces the concept of a virtual
> marker entirely.**
>
> Status: **mostly implemented; migration to finish.**

## The abstraction

```
 SkellyTracker keypoints  ──[ tracker→canonical mapping ]──▶  canonical landmarks  ──▶  standard human model
 (COCO-WholeBody, MediaPipe,                                  (neck_center, hips_center,     (segments, hierarchy,
  per-detector names)                                          left_elbow, …)                 rest pose — doc 12)
```

- **Keypoints** — a tracker's raw named outputs (`Keypoints`: `.xyz`, `.names`, `.visibility`). Tracker-specific.
- **Landmarks** — the canonical human model's points (the `tracked_points` in `canonical_body.yaml`).
  Tracker-agnostic. **Every landmark is first-class** — there are no "virtual" ones.
- **Mapping** — `TrackerMapping` (`skellytracker/core/io/tracker_mapping.py`): for each canonical landmark,
  how to produce it from tracker keypoints.

## The three mapping forms (the whole system, for now)

From `TrackerMapping` and the `*_to_canonical_mapping.yaml` files:

| Form | YAML | Meaning |
|---|---|---|
| **string** | `left_elbow: "left_elbow"` | 1:1 passthrough |
| **list** | `hips_center: ["left_hip", "right_hip"]` | unweighted mean |
| **dict** | `head_center: {left_ear: 0.5, right_ear: 0.5}` | weighted sum (normalized by present weights) |

Missing keypoints are silently skipped; list/dict use only present keypoints. That's the entire contract.
A landmark that used to be a "virtual marker" (e.g. `neck_center`) is now just a landmark whose mapping is a
list or dict.

## Ownership (the boundary)

- **SkellyTracker owns the mappings** — one `{tracker}_to_canonical_mapping.yaml` per tracker (rtmpose body,
  mediapipe body, hands, …). It also defines each tracker's keypoint names + connections.
- **SkellyForge owns the canonical model** — the landmark names + `segment_connections` + `joint_hierarchy` +
  `bone_length_ratios` + rest pose ([12](12-standard-human-model.md)). **No virtual markers.**
- The mapping references canonical landmark names (SkellyForge) on the left, tracker keypoint names
  (SkellyTracker) on the right. New tracker → add one mapping YAML; the canonical model is untouched.

## Current state

- ✅ **Body migrated.** `canonical_body.yaml` has `virtual_marker_definitions: null`; its 4 computed landmarks
  (`head_center`, `neck_center`, `trunk_center`, `hips_center`) are first-class `tracked_points`, produced by
  list-mean mappings in `rtmpose_body_to_canonical_mapping.yaml` / `mediapipe_body_to_canonical_mapping.yaml`.
- ✅ `TrackerMapping` implements the three forms and is what the realtime rigidifier + CoM already use.
- ⚠️ **Concept still lingers** in the SkellyModels Pydantic layer and some YAMLs — see the plan.

## Migration plan (finish killing "virtual marker") `[IN]`

1. **Remove the `virtual_markers` concept from the SkellyModels model layer**: drop
   `virtual_markers_definitions` from `AnatomicalStructure` and `AspectInfo`, the `VirtualMarkerDefinition`
   type (`skellymodels/utils/types.py`), its cross-field validation, and all usage (`aspect.py`,
   `trajectory.py`, `managers/actor.py`, `biomechanics/anatomical_calculations.py`). Delete outright (no
   shims), per the zero-vestigial-code rule.
2. **Migrate remaining YAMLs** that still declare virtual markers (candidates from the grep:
   `canonical_hand.yaml`, `rtmpose_model_info.yaml`, `mediapipe_model_info.yaml`) to the mapping form:
   computed landmarks become first-class in the canonical model; how each tracker produces them moves into
   that tracker's `*_to_canonical_mapping.yaml`.
3. **One canonical model per actor part** (body, hand, face) = a pure landmark list + anatomy; **one mapping
   per (tracker, part)** in SkellyTracker. That's the whole system.

## Deferred: richer mapping forms `[LATER]`

#TODO NOTE - NO! DO NOT DEFER! LETS MAKE A PLAN AND FIX AND DO THIS CORRECTLY!! 

The three forms are all **convex combinations** — they can only produce points *within* the input keypoints'
hull, so they **cannot produce a point offset off the body surface** (e.g. an anterior sternoclavicular joint;
see [12 — derived joint centers](12-standard-human-model.md#derived-joint-centers-and-the-clavicle)). A future
mapping form (frame-relative offset / cross-keypoint geometry) would cover that. **Deferred by decision** — do
not build it now; landmarks that need it use a best-available convex mapping in v1, with the limitation noted.

## Why this matters for the stream

The canonical landmark set defined here **is** what the [standard stream schema](09-standard-stream-protocol.md)
enumerates and what the [standard human model](12-standard-human-model.md) is built from. Unifying on one
mapping abstraction means "add a new tracker" never touches the canonical model, the schema, or any adapter —
it's one mapping YAML.
