# Conventions

The coordinate, rotation, and framing conventions every other layer assumes. Single-source: if another
doc needs one of these facts, it links here.

## Design principles

Two rules that decide arguments, stated once here.

### Sensible defaults, not required boilerplate

If a skeleton does not specify something that has one obviously-correct answer, **the default is the
specification**: a one-segment skeleton's rest pose is its segment's rest pose; a skeleton with no
declared mass distribution has an unweighted centre of mass. Authoring boilerplate to say the obvious
is how a format acquires a shape only one model can fill.

This does **not** loosen the repo's fail-loud rule, because a default and a fallback are different
things:

| | Resolved | Means | Verdict |
|---|---|---|---|
| **default** | once, at load | "you didn't say, and there is one right answer" | fine |
| **fallback** | per call, at runtime | "that didn't work, try something else" | still banned |

So a skeleton with no `joints:` gets a trivial rest pose (default), while a skeleton that asks for
XCoM without declaring mass raises **at load, naming the missing declaration** — never a quiet zero.

### Structure travels in the model, never in string patterns

If a consumer needs to know that four landmarks form an aruco square, or that a landmark belongs to
the face, the **skeleton declares it** — as a connection group or a landmark group. Nothing downstream
recovers structure by parsing a name. Names are opaque identifiers; a naming scheme that has to be
regex-able is a design that lost its structure somewhere upstream.

## World space

- **Units (authored):** proportions of the skeleton's **reference unit**, which each skeleton names.
  For the standard human that unit is body height: `H = 1.0` is ground plane to the top of the skull
  (`head_vertex`), anchored on the skull top rather than the hips so the proportions match
  anthropometric practice (de Leva, H from floor to vertex). For a charuco board it is the square
  length. Either way the template is size-agnostic and the **model-scale fit** supplies the size.
- **Units (measured):** millimetres. Tracked keypoints, calibrated cameras, and the wire carry mm. The
  boundary between the two is the **model-scale fit**
  ([../02-pipeline/model-scale-fitting.md](../02-pipeline/model-scale-fitting.md)): every visible
  segment reports `observed length / authored proportion`, those pool into one fitted scale, and a
  segment nobody can see is sized from it.
- **Scale is also a measurement.** A board authored at `square_length = 1.0` fits to the square length
  the cameras actually see, which is directly comparable to the value the user entered at calibration
  — the same machinery that sizes a human doubles as a calibration-error metric.
- **Handedness:** right-handed.
- **Axes:** **Blender's** — **+X right**, **+Y forward** (anterior), **+Z up** (ground plane at `z = 0`).
  SkellyForge authors everything in this frame (`coordinate_system: blender` in the top-level YAML).
  Tracker keypoints enter in FreeMoCap's older **+X forward / +Y left / +Z up** frame and are rotated
  once, at ingest, into Blender; nothing downstream converts again.
- **Other conventions** (VRM/glTF, ROS, ISB, Unreal, Unity, or user-defined) live in
  `definitions/coordinate_systems/coordinate_systems.yaml` and are entered/left ONLY at an I/O boundary,
  through `CoordinateSystemTransform` — never mid-pipeline.
- **Origin:** the rest pose places a skeleton's root segment at the world origin — `pelvis` for the
  human, whose feet then stand on one flat ground plane (enforced by test).

## Rotations

- **Quaternions are `wxyz`** (scalar-first), unit-norm.
- **Composition:** `q_child_local = conj(q_parent) · q_child_world`. The root's local equals its world;
  when the parent did not hydrate this frame, consumers fall back to world.
- **Identity == T-pose holds for fully-specified segments solving from their own rest positions** (the
  enforced form of the old stronger claim — see
  [../01-data-model/reference-geometry.md](../01-data-model/reference-geometry.md) for exactly what is
  guaranteed and why).
- **Rest orientation (authoring):** each segment carries a parent-relative `[w, x, y, z]` quaternion in
  `rest_pose.yaml`, defaulting to identity ("continues straight on from the parent") — never an euler
  triple, no order convention. Derived examples (clavicle posterior tilt, arms out, legs down, flat
  feet) are documented there.

## Segment-local frames

Each segment's rest frame is right-handed and declared by **name**, not slot:

- Local `+z` runs **proximal → distal** for every segment.
- The loader negates x-axis declarations on the right side so **both sides get local `+x` toward the
  subject's right**, `+y` forward, `+z` up — a right-handed triad cannot mirror all three axes, so
  `+x` is medial on the left and lateral on the right.
- The basis beyond `+z` comes from the segment's declared `reference_geometry` (origin + axis targets
  resolved by Gram-Schmidt) — never a fixed global axis.

## Mirroring

The left side is authored; the right side is generated by the loader's sidedness (`sided: true`
instantiates `left_*` + `right_*`) by **negating x-axis declarations** (see above). A basis is never
reflected — a reflected basis has `det = -1` and would silently mirror the model.

## Sources

Fresh from `skellyforge` (`core/skeleton/components/rigid_body_segment.py`,
`core/skeleton/loading/sided_expansion.py`, `definitions/human_skeleton/rest_pose.yaml`) + the
workspace `CLAUDE.md`.
