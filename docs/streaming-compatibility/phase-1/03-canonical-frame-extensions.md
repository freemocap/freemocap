# FMC-WS-3 — StandardHuman → StreamSchema

> **Build order: 1st** (unblocks FMC-WS-2). Depends on: SF-SH-1 (standard-human model), FMC-WS-1 (contract).
> **Status: ⏳ in progress.** The classmethod, `RestPose`, `max_persons` and the builder retirement landed
> (tests green). **The channel layout they landed against was superseded by
> [FMC-SR §2](07-spec-reconciliation.md#2-channel-groups--resolve-the-09-vs-03-conflict)** — the six-group
> layout in [09](../09-standard-stream-protocol.md#channels) is the target, and the keypoint/landmark split
> plus two-layer overlays are remaining scope. Adapter not wired.

## Goal

A single classmethod `StreamSchema.from_standard_human()` that enumerates every channel
from the canonical model. No separate builder functions, no adapter file, no large
parameter lists — the construction logic lives on the object it constructs.

After this workstream:
- `StreamSchema` has `from_standard_human(standard_human, ...)` as its primary constructor
- The schema declares the six channel groups of [09](../09-standard-stream-protocol.md#channels):
  measured `KEYPOINTS_3D` and the reconstructed segment model (`SEGMENT_ORIGINS` +
  `ROTATIONS_LOCAL` / `ROTATIONS_WORLD`) as separate groups
- The schema carries `segment_parents`, so local rotations compose into world placement
- Multi-subject is a first-class dimension (max_persons = 1 for now, subject_id on every sample)
- OVERLAY_2D blocks are per camera **per layer** (detections + reprojections), keyed by
  `(camera_id, overlay_layer)` in the block header
- The old `build_stream_schema()` and `stream_schema_builder.py` are retired

## Files

| File | Action |
|---|---|
| `freemocap/core/streaming/standard_stream/stream_schema.py` | **[evolve]** Rewrite `ChannelKind` to one member per group per [09](../09-standard-stream-protocol.md#channels); add `OverlayLayer`; add `segment_parents`; make the struct frozen. `from_standard_human()` + `RestPose.from_standard_human()` exist and are revised to carry tracker keypoints alongside segment origins. |
| `freemocap/core/streaming/standard_stream/stream_schema_builder.py` | **[retire]** The freestanding `build_stream_schema()` is replaced by `StreamSchema.from_standard_human()`. Tests updated. |
| `freemocap/core/pipeline/realtime/realtime_aggregator_node.py` | **[evolve]** Call `StreamSchema.from_standard_human()` on startup; store schema where the encoder can reach it. |

No new files. The old `skellyforge_adapter.py` idea is dead — freemocap imports skellyforge directly (that's the integration layer's job, per the cross-repo rule: freemocap CAN import skellyforge; skellyforge NEVER imports freemocap).

## Channel content — deferred to [09](../09-standard-stream-protocol.md)

> **Revised 2026-08-12 (FMC-SR §2).** This plan previously carried its own enumeration of the channel
> groups. It drifted from [09](../09-standard-stream-protocol.md) and then became the de-facto authority,
> because the code follows this file — which is how `POINTS` *and* `OVERLAY_2D` both ended up keyed by
> segment names. That was an SSOT bug: an implementation plan must not define the wire.
>
> **[09 § channels](../09-standard-stream-protocol.md#channels) is the single authority on channel content.**
> This plan implements against it; where they disagree, 09 wins and this file is what gets corrected.

Target layout in brief — the normative version, including landmark→segment attachment and the two overlay
layers, is in 09:

| # | Group | Names are |
|---|---|---|
| 0 | `KEYPOINTS_3D` | tracker keypoint names |
| 1 | `SEGMENT_ORIGINS` | segment names (transform origin = proximal joint) |
| 2 | `ROTATIONS_LOCAL` | segment names |
| 3 | `ROTATIONS_WORLD` | segment names |
| 4 | `DERIVED_POINTS` | `center_of_mass`, `xcom` |
| 5… | `OVERLAY_2D` | per camera × 2 layers (detections = keypoints, reprojections = segment model) |

**Landmarks are not on the stream** — `[LATER]`, possibly never. The current work is the segment layer.

**What the code does today, and why it changes:** `StreamSchema.from_standard_human()` passes
`standard_human.bone_names` to the skeleton `POINTS` group *and* to `OVERLAY_2D`. Tracker keypoints aren't
carried at all, the skeleton group isn't named as segment origins, and 2D overlays are keyed by segment name
when the detection layer is tracker keypoints. Correcting that is remaining scope for this workstream.

## Design decisions (locked)

### 1. One `block_kind` per channel group

No generic `ROTATIONS` kind. A rotation channel that doesn't declare its frame is exactly the ambiguity
[07](../07-coordinate-conventions.md#the-local-rotation-trap-vmc-and-unreal) warns about, and an enum member
kept "for backward-compat during transition" contradicts the zero-backwards-compat rule in
[00](../00-overview.md) — there is no shipped wire format to be compatible with. Wire values follow 09's
group order.

### 2. Classmethod on the target object

Instead of freestanding functions with large parameter lists:

```python
# OLD (sloppy):
schema = build_stream_schema(
    stream_id=..., stream_name=...,
    skeleton_point_names=..., rotation_bone_names=..., connections=...,
    joint_hierarchy=..., rest_pose=..., camera_ids=..., convention=...,
    derived_point_names=...,
)

# NEW (clean):
schema = StreamSchema.from_standard_human(
    stream_id=...,
    stream_name=...,
    standard_human=model,              # <- the single data source
    camera_ids=["cam0", "cam1", ...],  # <- topology, determined at startup
    convention=FREEMOCAP_CANONICAL_CONVENTION,
    max_persons=1,
)
```

The classmethod reads everything it needs from the model. No string of individual args
plucked from the model by a caller.

### 3. Multi-person from day one (spec doc 01)

The schema declares `max_persons` (1 for now). Every sample carries `subject_id` (0 for now).
When multi-person tracking lands, `max_persons` changes and `subject_id` gets real values —
the wire format doesn't change shape. This is exactly what the spec docs already call for.

### 4. OVERLAY_2D is per-camera (spec doc 09)

The schema declares ONE `OVERLAY_2D` channel group (same landmark names). The *sample*
carries ONE BLOCK PER CAMERA, each keyed by `camera_id` in the block header. Camera count
is set at stream creation (cameras connected at startup). A camera add/remove rebuilds the
stream (schema-on-change).

## Interface

```python
# stream_schema.py

class ChannelKind(IntEnum):
    """One member per channel group. Group semantics: 09 § channels."""

    KEYPOINTS_3D = 0     # tracker keypoint names — triangulated detections
    SEGMENT_ORIGINS = 1  # segment names — transform origin (proximal joint)
    ROTATIONS_LOCAL = 2  # segment names, wxyz — parent-relative (the VMC contract)
    ROTATIONS_WORLD = 3  # segment names, wxyz — world frame
    DERIVED_POINTS = 4   # center_of_mass, xcom
    OVERLAY_2D = 5       # per camera x layer


class OverlayLayer(IntEnum):
    """Which layer an OVERLAY_2D block carries (09 § 2D overlays)."""

    DETECTIONS = 0     # what the detector saw — tracker keypoint names
    REPROJECTIONS = 1  # the fitted segment model projected into this camera — segment names


class StreamSchema(msgspec.Struct, frozen=True):
    stream_id: str
    stream_name: str
    coordinate_convention: CoordinateConvention
    channels: tuple[ChannelGroup, ...]          # ordered, decoder indexes by position
    connections: tuple[tuple[str, str], ...]
    joint_hierarchy: dict[str, tuple[str, ...]]      # over segments
    segment_parents: dict[str, str]                  # segment -> parent segment
    rest_pose: RestPose | None
    camera_ids: tuple[str, ...]                # cameras connected at startup
    max_persons: int = 1                       # fixed at stream creation
    message_type: str = "stream_schema"

    @classmethod
    def from_standard_human(
        cls,
        *,
        stream_id: str,
        stream_name: str,
        standard_human: "StandardHuman",  # skellyforge import — freemocap's job
        camera_ids: Sequence[str] = (),
        convention: CoordinateConvention = FREEMOCAP_CANONICAL_CONVENTION,
        derived_point_names: Sequence[str] = ("center_of_mass", "xcom"),
        max_persons: int = 1,
    ) -> "StreamSchema":
        """Build the standard-stream schema from the canonical human model.

        Channel group order and content: 09 section "channels" (the authority).
        """
        keypoint_names = tuple(keypoint_names)                 # from the tracker mapping
        segment_names = tuple(standard_human.segment_names)
        units = convention.units.value

        channels: tuple[ChannelGroup, ...] = (
            ChannelGroup(
                kind=ChannelKind.KEYPOINTS_3D,
                names=keypoint_names,
                columns=("x", "y", "z", "reprojection_error"),
                units=units,
            ),
            # Transform origin (proximal joint), not the midpoint — this is what a
            # VRM/VMC bone transform's position is, so VMC needs no conversion.
            ChannelGroup(
                kind=ChannelKind.SEGMENT_ORIGINS,
                names=segment_names,
                columns=("x", "y", "z"),
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=segment_names,
                columns=("w", "x", "y", "z"),
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=segment_names,
                columns=("w", "x", "y", "z"),
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.DERIVED_POINTS,
                names=tuple(derived_point_names),
                columns=("x", "y", "z"),
                units=units,
            ),
            # OVERLAY_2D: one block per (camera_id, layer) in the sample.
            # DETECTIONS carry keypoint names; REPROJECTIONS carry segment names.
            ChannelGroup(
                kind=ChannelKind.OVERLAY_2D,
                names=keypoint_names + segment_names,
                columns=("x", "y", "visibility"),
                units="px",
            ),
        )

        # connections = parent→child edges from the bone hierarchy
        connections: list[tuple[str, str]] = []
        for bone in standard_human.bones:
            for child in standard_human.get_children(bone.name):
                connections.append((bone.name, child.name))

        hierarchy = {
            key: tuple(children)
            for key, children in standard_human.joint_hierarchy.items()
        }

        rest_pose = RestPose.from_standard_human(standard_human)

        return cls(
            stream_id=stream_id,
            stream_name=stream_name,
            coordinate_convention=convention,
            channels=channels,
            connections=tuple(connections),
            joint_hierarchy=hierarchy,
            rest_pose=rest_pose,
            camera_ids=tuple(camera_ids),
            max_persons=max_persons,
        )


class RestPose(msgspec.Struct, frozen=True):
    positions: dict[str, tuple[float, float, float]]
    reference_orientations: dict[str, tuple[float, float, float, float]]

    @classmethod
    def from_standard_human(
        cls, standard_human: "StandardHuman"
    ) -> "RestPose":
        """Build rest pose from the model's T-pose + identity orientations."""
        positions = {
            name: tuple(float(v) for v in pos)
            for name, pos in standard_human.t_pose_markers.items()
        }
        orientations = {
            name: (1.0, 0.0, 0.0, 0.0)   # identity == T-pose, wxyz
            for name in standard_human.segment_names
        }
        return cls(positions=positions, reference_orientations=orientations)
```

## Channel layout (sample block order)

The decoder maps sample blocks by position. Block order is fixed by `from_standard_human()` and declared in
`channels` — content per [09 § channels](../09-standard-stream-protocol.md#channels):

| Sample block idx | Kind | Names | Columns |
|---|---|---|---|
| 0 | `KEYPOINTS_3D` | tracker keypoint names | `x, y, z, reprojection_error` |
| 1 | `SEGMENT_ORIGINS` | segment names | `x, y, z` |
| 2 | `ROTATIONS_LOCAL` | segment names | `w, x, y, z` |
| 3 | `ROTATIONS_WORLD` | segment names | `w, x, y, z` |
| 4 | `DERIVED_POINTS` | `center_of_mass`, `xcom` | `x, y, z` |
| 5 … 5+2C-1 | `OVERLAY_2D` | keyed by `(camera_id, overlay_layer)` in the block header; DETECTIONS carry keypoint names, REPROJECTIONS carry segment names | `x, y, visibility` |

`C` = cameras connected at startup. The sample carries **2C** overlay blocks — one per camera per layer.
The decoder groups them by `(camera_id, overlay_layer)` from each block header.

## Task checklist

Items 1–5 and 7 landed against the *previous* channel layout and are re-opened by FMC-SR §2.

1. [ ] **Rewrite `ChannelKind`** — one member per channel group per 09; add `OverlayLayer`. Delete the
      legacy `ROTATIONS` member (defect D10) and renumber; there is no shipped wire to stay compatible with.
2. [x] **`from_standard_human()` classmethod** on `StreamSchema` — exists; **must be revised** to split
      keypoints from landmarks and stop keying overlays by segment name.
3. [x] **`from_standard_human()` classmethod** on `RestPose`.
4. [x] **`max_persons` field** on `StreamSchema`.
5. [x] **`stream_schema_builder.py` retired** — replaced by the classmethod.
6. [ ] **Add `segment_parents`** to `StreamSchema` — with `rest_pose`, this is what lets a consumer compose
      the local-rotation chain into world placement (the VMC/VRM model).
7. [ ] **Make `StreamSchema` frozen** — specified `frozen=True` here, mutable in code (defect D22).
8. [ ] **Wire the aggregator** — call `StreamSchema.from_standard_human()` at startup, cache the result
      where FMC-WS-2's encoder can access it.
9. [ ] **Update builder tests** — cover all six groups, both rotation kinds, the keypoint/landmark split,
      the two overlay layers, attachment map, hierarchy, and `RestPose`.

## Tests

- `test_from_standard_human` — minimal model (hips+spine+head) → schema with 5 + C channel groups,
  both rotation groups, correct bone names, RestPose positions populated, identity orientations.
- `test_rotation_groups_distinct_kinds` — world block kind=3, local block kind=4.
- `test_connections_from_hierarchy` — parent→child edges match model's `joint_hierarchy`.
- `test_max_persons_default` — schema.max_persons = 1.
- `test_camera_ids_in_schema` — camera_ids match what was passed; OVERLAY_2D block count in
  sample = len(camera_ids).

## NOT in scope

- WebSocket wiring (FMC-WS-2).
- Per-frame sample encoding (FMC-WS-2).
- UI changes (FMC-WS-4).
- Changes to `StandardHuman` or bone definitions (SF-SH-1 is done).
