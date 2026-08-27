# Generic Skeletons — the charuco board as the forcing function

**Describes:** why a charuco board is a `SkeletonDefinition`, what integrating it end to end changes
about the rest of the system, and which single-human assumptions it exists to remove. Vocabulary in
[../00-foundation/glossary.md](../00-foundation/glossary.md); principles in
[../00-foundation/conventions.md](../00-foundation/conventions.md).

## Why the board

FreeMoCap has always been meant to track multiple people and multiple *kinds* of object. Through the
streaming rebuild the code drifted toward "the only thing we track is one human" — not by decision,
but because the human was the only thing exercising the code, and nothing was written down saying it
was one case rather than the case.

The board is the cheapest possible second case that breaks every wrong assumption at once. It has:

- **one segment**, so anything requiring joints, chains or a tree breaks;
- **no anatomy**, so anything requiring de Leva mass or named body parts breaks;
- **its own reference unit**, so anything assuming "scale means body height" breaks;
- **landmark-level structure** (a grid, quads), so anything assuming edges are segment-level breaks;
- **no keypoint→landmark remapping**, so anything requiring an authored mapping per point breaks.

The goal is not "make the board work". It is to make it work by *generalizing what already exists*,
so the next object is cheap. Duplication, board-specific branches, and string-parsing are failures.

## The board as a skeleton

| Layer | The board |
|---|---|
| keypoint | `charuco` detector output: interior corners + each aruco marker's four corners |
| mapping | **pass-through** — the markers *are* the landmarks ([../01-data-model/tracker-mapping.md](../01-data-model/tracker-mapping.md)) |
| landmark | one per marker, `local_position` from the board's own geometry on the `z = 0` plane |
| segment | one, fully specified from three non-collinear markers → rigid (Umeyama) fit |
| linkage / chain | none — a rigid skeleton has none, and that is complete, not deficient |
| skeleton | one segment + its markers + its landmark/connection groups |

Hydration needs **nothing new**: a one-segment, N-landmark skeleton fit over its observed markers is
exactly a board pose plus a scale, from the same closed form the skull and pelvis already use.

**Authored proportionally, normalized to square length = 1.0** — the exact parallel of the human's
`H = 1.0`. The fitted scale then *is* the measured square length in millimetres, which is directly
comparable to the value the user typed at calibration. The board's scale is not a nuisance to
special-case; it is the capture volume's own scale, and comparing fitted against entered is a
reconstruction-error metric that falls out for free
([../02-pipeline/model-scale-fitting.md](../02-pipeline/model-scale-fitting.md)).

Both shipped boards — the default 5x3 and the legacy 7x5 — are the *same* skeleton built from
different parameters. Supporting a third is a config change, not code.

## What this changes elsewhere

### Structure moves into the model

A board's edges are landmark-to-landmark (grid lines, marker quads), not segment-to-segment. So
`ModelDefinition` grows **landmark connection groups** and **landmark groups**, each carrying
ordered **tags** — `left`, `[eye, face]`, `aruco_marker` — which a palette turns into a colour
([../01-data-model/message-contract.md](../01-data-model/message-contract.md)). Tags rather than
colours because the model should say what a thing IS, not what it should look like: that is what lets
a user recolour a whole skeleton by editing one mapping, and it keeps a presentation choice out of a
geometry file. The palette lives in skellyforge, since skellyforge is what owns the things being
coloured and cannot import the packages that would otherwise hold the answer.

This is not a board feature — the human's skull outline is authored the same way, as the worked
example. And it retires two places where structure was being recovered by parsing names: rebuilding
aruco quads by splitting `ArucoMarkerCorner-{id}-{j}`, and colouring points by
`startsWith('arucomarkercorner')`. Once structure travels in the model, **names are opaque
identifiers** and the point-naming scheme stops being load-bearing.

### Under-specified skeletons get defaults, not errors

A one-segment skeleton has no joint tree, and today `RestPose` refuses it outright. The real
invariant is *the joint tree must resolve to exactly one root*, which one segment satisfies
trivially. Likewise it has no declared mass, and gets the unweighted-mean CoM
([../02-pipeline/biomechanics-layer.md](../02-pipeline/biomechanics-layer.md)).

### The pipeline stops assuming one of anything

The wire has always been plural — `models`, `instances` and `trackers` are tuples — but the
composition layer collapsed it to one hardcoded human instance. The pipeline carries one bundle per
tracked skeleton (definition + rest pose + mapping + scale fitter + optional roll resolver), and
every producer loops over them ([../02-pipeline/realtime-loop.md](../02-pipeline/realtime-loop.md)).

Multiple *people* fall out of the same change as several instances sharing one model. This work only
exercises multiple models, but must not re-close that door.

### The frontend collapses to one connection renderer, and one plural channel

Two connection renderers existed. The schema-driven one was **inert in the live path** — the tracker
schema it needed was only ever dispatched to the viewport worker by the playback provider — while the
model-driven one did the actual drawing. Both are gone, replaced by a single `ModelConnectionRenderer`
that draws segment edges and landmark connection groups alike, in their resolved colours. Playback
moved onto the same path: a recording's tracked points and name-pair edges are just an under-specified
model, so `playback-model-frame.ts` expresses it as one rather than keeping a second renderer alive.

The deeper fix was upstream of the renderers. Segment origins, rotations, fitted lengths and derived
points were four *singular* frame channels, each silently labelled from `models[0]`'s symbol table.
They are now one plural `models: ResolvedModelFrame[]`, and every renderer iterates it
([../04-ui/ui-integration.md](../04-ui/ui-integration.md)).

## What it looks like when it works

- **2D** — charuco corners and aruco markers overlaid on every camera, from the same `OVERLAY_2D`
  channel the pose detector uses, under its own tracker observation.
- **3D, measured** — the triangulated corners as keypoints.
- **3D, reconstructed** — the board as a rigid object: one fitted pose, its markers placed by the fit
  rather than by triangulation noise, grid in one colour and marker quads in another.
- **The fitted square length** reported next to the entered one.

### What one frame actually carries

Decoded from a real composed frame with a person and a 5x3 board in it:

```
models:    ['standard_human', 'charuco_board']
instances: [(0, 'standard_human', 1684.15 mm), (1, 'charuco_board', 54.00 mm)]
trackers:  [('rtmpose', 'rtmpose', 'standard_human'), ('charuco', 'charuco', 'charuco_board')]

charuco_board   scale_reference=square_length   segments=1 landmarks=36
  landmark_group   charuco_corners   n=8    #14ff14
  landmark_group   aruco_corners     n=28   #ff8c14
  connection_group charuco_grid      n=10   #14ff14
  connection_group aruco_markers     n=28   #ff8c14
```

The board's `fitted_scale_mm` of 54.00 is the *measured* square length against an entered 54 — the
reconstruction-error metric, with no board-specific code path producing it. The human alongside it
reports 1684 mm of body height from the identical machinery, each against the unit its own model
names.

## Why this comes before the posthoc rebuild

The offline paths are being rebuilt from scratch anyway. Doing that against a human-shaped model layer
would bake the same assumptions into a second pipeline, and posthoc handles boards already (its dead
`charuco_model_from_observations.py` is a board reconstruction). Landing the generic layer first means
posthoc gets rebuilt once, on foundations that already hold more than one kind of thing
([../02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md)).
