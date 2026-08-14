# 13 — Keypoint → Landmark Mapping (the SkellyTracker ↔ SkellyForge boundary)

> **This doc is the Single Source of Truth for the keypoint / landmark / segment distinction.** Every other
> doc uses these terms as defined here and links back rather than redefining them.
>
> It describes the boundary between **SkellyTracker** (which produces *keypoint trajectories*) and
> **SkellyForge** (which produces *landmark trajectories* on *segments*). The mapping is the **single**
> abstraction for "how does a tracker's output become the standard human."
>
> Status: **implemented (realtime); posthoc consumer to follow.**

## Two kinds of trajectory

This is the organizing fact of the whole system. There are **two kinds of 3D trajectory**, they are
produced by different repos, and confusing them is the source of most of the ambiguity this spec folder
has had to correct.

| Term | What it is | Produced by | Owned by |
|---|---|---|---|
| **Keypoint trajectory** | A point **tracked in 2D by a detector and triangulated to 3D**. Named by the tracker that produced it. A raw observation of the world. | detectors → triangulation | **SkellyTracker** |
| **Landmark trajectory** | The 3D trajectory of a specific feature **on a segment** of the model we fit to the keypoints. A landmark *is a point on a segment* — its segment attachment is intrinsic, not incidental. | model fitting | **SkellyForge** |
| **Segment** | A 3D-oriented rigid body of the fitted model. Carries its landmarks, a reference geometry, a **transform origin** (its proximal joint) and an orientation. | model fitting | **SkellyForge** |

> **What the stream carries today: keypoints and *segments*, not landmarks.** The standard stream ships
> `KEYPOINTS_3D` (the measurement) plus `SEGMENT_ORIGINS` and the rotation groups (the reconstruction) —
> see [09 § channels](09-standard-stream-protocol.md#channels). Landmarks are a model-layer concept that is
> **`[LATER]`, possibly never on the wire**; the current work is the segment layer. The distinction below
> still matters because it defines the repo boundary — the mapping files turn keypoints into the canonical
> points the segment model is fitted from.

> A keypoint is **measured**. A landmark is **fitted** — it is where the model says that anatomical feature
> is, given the keypoints. They are different things even when they share a name: `left_elbow` the keypoint
> is a detector's estimate; `left_elbow` the landmark is a point on the fitted forearm segment.

**The mapping files are the entire interface between the two repos.** Keypoints in, landmarks out:

```
 SkellyTracker                    │  the boundary  │              SkellyForge
                                  │                │
 keypoint trajectories  ──[ {tracker}_to_canonical_mapping.yaml ]──▶  landmark trajectories
 (COCO-WholeBody, MediaPipe,      │                │              (points on segments)
  per-detector names)             │                │                        │
                                  │                │                        ▼
                                  │                │              segments: hierarchy,
                                  │                │              reference geometry,
                                  │                │              orientation — doc 12
```

- **Keypoints** — a tracker's raw named outputs (`Keypoints`: `.xyz`, `.names`, `.visibility`).
  Tracker-specific. SkellyTracker names them.
- **Landmarks** — the canonical model's points (the `tracked_points` in `canonical_body.yaml`).
  Tracker-agnostic, segment-attached. **Every landmark is first-class.**
- **Mapping** — `TrackerMapping` (`skellytracker/core/io/tracker_mapping.py`): for each canonical landmark,
  how to produce it from tracker keypoints.

Both kinds of trajectory travel on the standard stream as separate channel groups — the stream carries
everything and lets consumers subset ([09](09-standard-stream-protocol.md)).

### Segments, not anatomical bones (current scope)

We are **not** currently working at the level of anatomical bones. We fit **3D-oriented segments** matched
to the **VRM 1.0** schema — the level of abstraction that avatar/streaming formats like VMC operate at.
Anatomically-aligned bone models come **`[LATER]`**. Where the code says `HumanBone` / `human_bones.py` /
`BONE_ALIASES`, that is VRM's vocabulary, not a claim about skeletal anatomy. See
[12 — scope](12-standard-human-model.md#segments-not-anatomical-bones).

## The three mapping forms (the whole system, for now)

From `TrackerMapping` and the `*_to_canonical_mapping.yaml` files:

| Form | YAML | Meaning |
|---|---|---|
| **string** | `left_elbow: "left_elbow"` | 1:1 passthrough |
| **list** | `hips_center: ["left_hip", "right_hip"]` | unweighted mean |
| **dict** | `head_center: {left_ear: 0.5, right_ear: 0.5}` | weighted sum (normalized by present weights) |

Missing keypoints are silently skipped; list/dict use only present keypoints. That's the entire contract.
A computed landmark (e.g. `neck_center`) is simply a landmark whose mapping is a list or dict.

## Ownership (the boundary)

- **SkellyTracker owns the mappings** — one `{tracker}_to_canonical_mapping.yaml` per tracker (rtmpose body,
  mediapipe body, hands, …). It also defines each tracker's keypoint names + connections.
- **SkellyForge owns the canonical model** — the landmark names + `segment_connections` + `joint_hierarchy` +
  `bone_length_ratios` + rest pose ([12](12-standard-human-model.md)).
- The mapping references canonical landmark names (SkellyForge) on the left, tracker keypoint names
  (SkellyTracker) on the right. New tracker → add one mapping YAML; the canonical model is untouched.

## Current state

- **Body + hands.** `canonical_body.yaml` / `canonical_hand.yaml` list every landmark as a first-class
  `tracked_point`; the 4 computed body landmarks (`head_center`, `neck_center`, `trunk_center`,
  `hips_center`) are produced by list-mean mappings in `rtmpose_body_to_canonical_mapping.yaml` /
  `mediapipe_body_to_canonical_mapping.yaml`.
- `TrackerMapping` implements the three forms and is what the realtime rigidifier + CoM use.
- The SkellyModels model layer (`AnatomicalStructure` / `AspectInfo` / `Trajectory`) carries only
  first-class landmarks.
- **One canonical model per actor part** (body, hand, face) = a pure landmark list + anatomy; **one mapping
  per (tracker, part)** in SkellyTracker. That is the whole system.

## Remaining work `[IN]`

The realtime path is fully on this mapping. The **posthoc** `Human` pipeline still builds from the legacy
tracker model-infos (`rtmpose_model_info.yaml` / `mediapipe_model_info.yaml`); route it through the same
`*_to_canonical_mapping.yaml` + the canonical model, and retire those tracker model-infos.

## Richer mapping form: `anatomical_offset` (local-basis offset) `[IN]`

The three convex forms above can only produce points *inside* the keypoints' hull, so they cannot place a
joint center that sits **off** the marked surface — the anterior sternoclavicular joint (clavicle base), the
glenohumeral joint, hip joint centers. Those are **real and required**
([12 — derived joint centers](12-standard-human-model.md#derived-joint-centers-and-the-clavicle)), so we add a
fourth form **now** rather than deferring it.

**`anatomical_offset` — a derived landmark placed by an anthropometric offset in a local anatomical frame.** Still a
**deterministic geometric function of tracker keypoints** — no optimization, no runtime fitting:

1. **Origin** — a landmark or convex-combo (e.g. `mean(left_shoulder, right_shoulder)`).
2. **Frame** — a right-handed local frame from reference landmarks, exactly as `bs/`'s
   `CoordinateFrameDefinition` builds one (one *exact* axis, one *approximate*, third via cross-product). For
   the trunk: up = `hips_center → neck_center` (exact), lateral = `left_shoulder → right_shoulder`
   (approximate) → **anterior = up × lateral**.
3. **Offset** — a vector in that frame whose magnitude is an **anthropometric ratio × a reference length**
   (e.g. a fraction of biacromial/shoulder width), so it **scales with the subject** — same anthropometry that
   seeds `bone_length_ratios`. **Never runtime-fit** (per the standard-human decision).

The one definition is evaluated per-frame (the live landmark) *and* on the rest skeleton (the T-pose position)
— one function, both uses. Illustrative:

```yaml
sternoclavicular:                    # canonical landmark
  form: anatomical_offset
  origin: ["left_shoulder", "right_shoulder"]     # mean → frame origin
  frame:                                          # bs/ CoordinateFrameDefinition style
    up:      { from: hips_center, to: neck_center,        kind: exact }
    lateral: { from: left_shoulder, to: right_shoulder,   kind: approximate }
  offset:  { anterior: 0.15, up: -0.05 }          # ratios of reference_length
  reference_length: shoulder_width
```

One form covers the SC joint, the GH joint, hip joint centers, and later the scapula
([12](12-standard-human-model.md)). Exact YAML schema is finalized in implementation; the contract is
*origin + a landmark-defined frame + an anthropometric offset*, deterministic and subject-scaled. These are
still **landmarks** produced from **keypoints** — `anatomical_offset` is simply a richer mapping form.

## Why this matters for the stream

The canonical landmark set defined here **is** what the [standard stream schema](09-standard-stream-protocol.md)
enumerates and what the [standard human model](12-standard-human-model.md) is built from. Unifying on one
mapping abstraction means "add a new tracker" never touches the canonical model, the schema, or any adapter —
it's one mapping YAML.
