# Model-Scale Fitting

**Describes:** how a dimensionless skeleton gets a size — skellyforge's
`core/skeleton/pose/model_scale_fitting.py`, the per-segment scale every hydrated pose carries,
and how the realtime aggregator drives them. Applies to **every** skeleton, human or not.

## The problem it solves

Landmarks are authored as fractions of the skeleton's own **reference unit** — reference scale for
the human (`H = 1.0`, floor to skull top), square length for a charuco board — so a template
describes a shape and not a thing. Turning it into a thing means answering one question —
**how big is this one** — under the condition that a camera rarely sees all of it. Seated at a
desk, a person has no knees, ankles or feet; a board is often half out of frame.

## The idea

The authored proportion `p` makes every visible segment an answer to the *same* question. A
segment observed to be `d` long reports

```
s = d / p        world units per unit of the model's reference unit
```

and that is the model's size, read off that one segment. So the fit is not "measure lengths,
then guess a size". It is **one scale field over the skeleton**:

```
Ŝ   = robust aggregate of the readings from segments that actually measure something
s̃ₛ  = that segment's own reading, shrunk toward Ŝ by how much evidence it has
Lₛ  = pₛ · s̃ₛ
```

A segment nobody can see has no reading, so `s̃ₛ` **is** `Ŝ` and its length is `pₛ · Ŝ`. That is
not a fallback — it is the answer a proportional template exists to give. Segment length and
overall size are not two estimators to reconcile; they are the same number viewed through `pₛ`.

Nothing in the fit measures a floor, assumes anything is standing, or needs a calibration pose.

## What the fitted scale MEANS

`ModelDefinition.scale_reference_name` says what the model's `1.0` is, so one number reads
correctly for every skeleton:

| Skeleton | `1.0` is | Fitted scale is |
|---|---|---|
| standard human | reference scale | the subject's stature in mm |
| charuco board | square length | the board's measured square length in mm |

The board case is not a curiosity — **it is the calibration's own scale.** The user types the
square length during calibration and that number defines the scale of the whole capture volume,
so the fitted square length is directly comparable to the entered one. The same machinery that
sizes a person doubles as a reconstruction-error metric, with no board-specific code path.

## Where the readings come from

`SegmentPose.scale_estimate`, filled by hydration, so every hydrated segment is
self-describing about its size:

| Solve | Scale it reports |
|---|---|
| rigid fit (5 segments: `pelvis`, `thoracic`, `skull`, `left/right_carpals`) | the Umeyama similarity scale, measured over every observed landmark at once |
| direction fit (the other 56) | `‖primary − origin‖ / segment.length` |

The rigid fit is a **similarity**, not a rigid motion, precisely because the template is
dimensionless: `align_point_sets_similarity` recovers scale from the same SVD as the
rotation. Solving without it does not merely lose the size — the translation absorbs the
mismatch (`observed_centroid − R·reference_centroid` lands on the observed centroid when the
reference is a thousand times smaller), so the segment's **origin** goes to the wrong place.

## Who is allowed to vote

Not every segment measures the subject. The tracker mapping *constructs* a good many
landmarks as `ratio × reference_length` along an authored direction — the sternoclavicular
joints, the xiphoid process, the chest and neck centres. A segment between two of them
reports an authored ratio times a span measured elsewhere: the template quoting itself back.
Worse, such a segment is nearly noise-free, so a consistency-weighted estimator would rank it
as the best evidence available.

`TrackerMapping.directly_measured_landmark_names` names what the mapping measures rather than
constructs (every non-offset form is an affine combination of measured keypoints with
constant coefficients, so it carries the subject's real geometry).
`scale_voting_segment_names` turns that into the segments those make measurable — a
rigid-fit segment needs **all** of its landmarks measured, a direction-fit one needs its
origin and primary. For rtmpose that is 40 segments: the four long limb bones per side, the
heels, and the finger phalanges. No spine, clavicle, pelvis, thorax or skull.

Non-voting segments still keep their own measured `s̃ₛ`, because their length is where their
endpoints actually are — a bone drawn at `pₛ · Ĥ` when its own landmarks say otherwise would
not reach its own joints.

## What makes it robust

- **Medians throughout, never means.** One badly triangulated frame must not stretch a bone;
  one badly tracked limb must not resize the body. A weighted mean lets an outlier pull; a
  weighted median lets it vote once.
- **Weights are derived, not dialled.** A segment's vote is worth `p²` (a fixed absolute error
  on `d` is a relative error on `s = d/p` that grows as `1/p`, so short segments genuinely know
  less — this is the inverse-variance weight), times its sample count, over its relative
  dispersion. No hand-written table of which bones to trust; the fingers fall ~700× below a
  femur on their own.
- **Bilateral pooling for the height, per-side lengths.** A one-sided occlusion is ordinary and
  stature is not sided, so left and right pool their readings into one vote. Their *lengths*
  stay separate, so a real limb-length difference survives the fit.
- **Shrinkage toward the pooled scale.** `λ = n / (n + κ)` with `κ` scaled by dispersion: with
  no readings a segment is entirely the template, at `SHRINKAGE_PRIOR_SAMPLES` clean readings it
  is half its own measurement, past that mostly itself. Noisier readings buy less.
- **One temporal mechanism.** A bounded per-segment window (`segment_scale_window_frames`,
  default 30 — about a second at 30fps) is the *only* smoothing. Each segment's median over its
  window is already steady, so the height pooled from those medians is steady too, with no
  second filter to tune or to lag.
- **A segment that stops being seen keeps its window.** Your femur is the same length sitting
  down as standing up; dropping the measurement when a desk hides it would make the height jump
  for no anatomical reason. `reset` is how a caller says the body itself changed.

## No scale is a state, not a default

`has_model_scale` is False while no measurable segment has ever been seen. Then there are no
millimetres, and the aggregator publishes none — `segment_lengths` empty, `fitted_scale_mm`
`None` — rather than a plausible-looking nominal. `current_fit()` raises
`InsufficientScaleEvidence` if asked anyway.

## Where it runs

The aggregator builds one `StreamingModelScaleFitter` per run (rebuilt on detector change,
since which landmarks are measured is a property of the mapping), calls `observe_pose` after
roll resolution, and fits once per frame. The fit feeds three consumers:

1. `landmark_world_positions(segment_scales=…)` — the center of mass places landmarks from
   their **proportional** local positions, so without the scale every landmark collapses onto
   its segment's origin and the CoM becomes a mass-weighted average of joint centres.
2. the `SEGMENT_LENGTHS` channel — fitted millimetres for **every** segment, seen or not.
3. `ModelInstance.fitted_scale_mm` — the instance's size, since the model definition is
   dimensionless (`RestSegment.length_proportion`).

Reset paths: the skeleton-fit reset signal, and calibration hot-reload (every reading in the
windows was measured in the old frame's units).

Posthoc parity note: batch posthoc uses the full-recording window once the posthoc rebuild
lands ([posthoc-rebuild.md](posthoc-rebuild.md)).

## Measured behaviour

Synthetic rtmpose keypoints through the real mapping
(`freemocap/tests/test_model_scale_in_the_loop.py`):

| | fitted height | voting segments | `left_foot` | femur |
|---|---|---|---|---|
| standing | 1684.2 mm | 10 | 155.1 mm | 450.1 mm |
| at a desk (no knees/ankles/heels/toes) | 1650.0 mm | 4 (both arms only) | 155.3 mm | 441.0 mm |

The foot nobody can see comes out 0.2mm from what it measures when visible, inferred from
forearms and upper arms alone.
