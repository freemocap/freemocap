# Segment Lengths (derived nominal, then estimated per-segment per frame)

**Describes:** how a segment length is obtained. Each segment has a **derived nominal** length (from
its primary direction target `rest_position`) that is then **refined per frame** by a per-segment
rolling-median estimator over the live landmarks.

## What this covers

`RigidBodySegment.length` = `|distal.rest_position|` (the primary direction target, authored in the
segment own local frame) is the **empty-window seed**. `estimate_segment_lengths` (a pure
`(result, state)` action in skellyforge kinematics) measures each segment origin-to-distal distance
from the hydrated landmarks, holds a rolling window (`window_seconds`: 2.5 s realtime, unbounded
posthoc), and returns the per-segment median. Each segment adapts to the live subject true
proportions **independently** — no single uniform scale — falling back to the seed while unobserved.

## Status

`estimate_segment_lengths` feeds the T-pose build (`build_standard_human_tpose(..., lengths=...)`)
and the rigidifier in the realtime loop; the frontend renders from the live `SEGMENT_LENGTHS` channel.
