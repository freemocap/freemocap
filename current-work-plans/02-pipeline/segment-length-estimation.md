# Segment Lengths (derived, not estimated)

**Describes:** how a segment's length is obtained. In the new ontology, length is **derived** from the
segment's exact-axis target landmark's `rest_position`.

## What this covers

`RigidBodySegment.length` = `|distal.rest_position|` (the exact-axis target, authored in the segment's
own local frame). Subject scaling is a uniform scale of every `rest_position`.

## Status

Length is derived from position (see [segment-model.md](../01-data-model/segment-model.md)).
