# Reference Geometry (the standard-human T-pose)

**Describes:** the **T-pose** each live pose is measured against (`identity == T-pose`). In the new
ontology this is **`StandardHumanTPose`**, built from `RigidBodySegment` + `AnatomicalLandmark` —
length derived from `rest_position`.

## What this covers

The built T-pose: every segment's reference geometry (origin / basis / length) + every landmark's rest
position, at identity. One build serves both the orientation solver and the rest-pose message.

## Key facts

- Each landmark's `rest_position` is authored **once**, in its `reference_frame`'s local frame (see
  [segment-model.md](segment-model.md)).
- A segment's `length` is **derived** from its primary direction's target `rest_position`.
- The rest frame (basis) is built from the segment's axes — the primary direction (hard seed) + the
  twist direction (soft hint), Gram-Schmidt'd.
- The **skull is non-degenerate by construction**: the eyes / ears / nose are authored as distinct
  anterior / lateral landmarks on the head, so the head is a full 7-point rigid body.
- The **face is not part of the segment tree** — it is 52 ARKit blendshapes (`FaceBlendShapes`).

## Status

The T-pose build (`build_standard_human_tpose` → `StandardHumanTPose`) is landed. The old
`dead_reference_geometry.py` is slated for deletion (see IMPLEMENTATION_PLAN.md).
