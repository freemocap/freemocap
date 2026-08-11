# FMC-WS-3 — StandardHuman → StreamSchema

> **Build order: 1st** (unblocks FMC-WS-2). Depends on: SF-SH-1 (standard-human model), FMC-WS-1 (contract).
> **Status: ✅ builder done (4 tests green), ⏳ adapter not wired.**

## Goal

A single classmethod `StreamSchema.from_standard_human()` that enumerates every channel
from the canonical model. No separate builder functions, no adapter file, no large
parameter lists — the construction logic lives on the object it constructs.

After this workstream:
- `StreamSchema` has `from_standard_human(standard_human, ...)` as its primary constructor
- The schema carries ROTATIONS_WORLD + ROTATIONS_LOCAL as distinct channel kinds
- Multi-subject is a first-class dimension (max_persons = 1 for now, subject_id on every sample)
- OVERLAY_2D blocks are per-camera (one block per camera_id in the sample, keyed by camera_id in the block header)
- The old `build_stream_schema()` and `stream_schema_builder.py` are retired

## Files

| File | Action |
|---|---|
| `freemocap/core/streaming/standard_stream/stream_schema.py` | **[evolve]** Add `ROTATIONS_WORLD=3`, `ROTATIONS_LOCAL=4` to `ChannelKind`. Add `from_standard_human()` classmethod + `RestPose.from_standard_human()` classmethod. |
| `freemocap/core/streaming/standard_stream/stream_schema_builder.py` | **[retire]** The freestanding `build_stream_schema()` is replaced by `StreamSchema.from_standard_human()`. Tests updated. |
| `freemocap/core/pipeline/realtime/realtime_aggregator_node.py` | **[evolve]** Call `StreamSchema.from_standard_human()` on startup; store schema where the encoder can reach it. |

No new files. The old `skellyforge_adapter.py` idea is dead — freemocap imports skellyforge directly (that's the integration layer's job, per the cross-repo rule: freemocap CAN import skellyforge; skellyforge NEVER imports freemocap).

## Design decisions (locked)

### 1. Two rotation channel kinds

`ChannelKind.ROTATIONS_WORLD = 3`, `ChannelKind.ROTATIONS_LOCAL = 4`. Same `names` (bone canonical names), different `kind` bytes. Decoder skips what it doesn't need.

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
    POINTS = 0
    ROTATIONS = 1          # legacy — kept for transition
    OVERLAY_2D = 2
    ROTATIONS_WORLD = 3    # NEW
    ROTATIONS_LOCAL = 4    # NEW


class StreamSchema(msgspec.Struct, frozen=True):
    stream_id: str
    stream_name: str
    coordinate_convention: CoordinateConvention
    channels: tuple[ChannelGroup, ...]          # ordered, decoder indexes by position
    connections: tuple[tuple[str, str], ...]
    joint_hierarchy: dict[str, tuple[str, ...]]
    rest_pose: RestPose | None
    camera_ids: tuple[str, ...]                # cameras connected at startup
    max_persons: int = 1                       # reserved for multi-subject
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

        Enumerates channels in order:
          0. SKELETON_POINTS  — bone proximal joints, cols (x, y, z, reprojection_error)
          1. DERIVED_POINTS   — center_of_mass, xcom; cols (x, y, z)
          2. ROTATIONS_WORLD  — per-bone world-frame quaternion, cols (w, x, y, z)
          3. ROTATIONS_LOCAL  — per-bone parent-relative quaternion, cols (w, x, y, z)
          4. OVERLAY_2D       — per-camera (one block per camera_id in sample),
                                cols (x, y, visibility)
        """
        bone_names = tuple(standard_human.bone_names)
        units = convention.units.value

        channels: tuple[ChannelGroup, ...] = (
            ChannelGroup(
                kind=ChannelKind.POINTS,
                names=bone_names,
                columns=("x", "y", "z", "reprojection_error"),
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.POINTS,
                names=tuple(derived_point_names),
                columns=("x", "y", "z"),
                units=units,
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_WORLD,
                names=bone_names,
                columns=("w", "x", "y", "z"),
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.ROTATIONS_LOCAL,
                names=bone_names,
                columns=("w", "x", "y", "z"),
                units="quaternion",
            ),
            ChannelGroup(
                kind=ChannelKind.OVERLAY_2D,
                names=bone_names,
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
            name: (1.0, 0.0, 0.0, 0.0)   # identity == T-pose
            for name in standard_human.bone_names
        }
        return cls(positions=positions, reference_orientations=orientations)
```

## Channel layout (sample block order)

The decoder maps sample blocks by position. Block order is fixed by `from_standard_human()`
and declared in `channels`:

| Sample block idx | Kind | Names | Columns |
|---|---|---|---|
| 0 | POINTS | bone canonical names | `x, y, z, reprojection_error` |
| 1 | POINTS | `center_of_mass`, `xcom` | `x, y, z` |
| 2 | ROTATIONS_WORLD | bone canonical names | `w, x, y, z` |
| 3 | ROTATIONS_LOCAL | bone canonical names | `w, x, y, z` |
| 4…4+C-1 | OVERLAY_2D | bone canonical names, keyed by camera_id in block header | `x, y, visibility` |

`C` = number of cameras connected at startup. The sample carries one OVERLAY_2D block per camera.
The decoder groups them by `camera_id` from each block header.

## Task checklist

1. [ ] **Extend `ChannelKind`** — add `ROTATIONS_WORLD = 3`, `ROTATIONS_LOCAL = 4`.
2. [ ] **Add `from_standard_human()` classmethod** to `StreamSchema`.
3. [ ] **Add `from_standard_human()` classmethod** to `RestPose`.
4. [ ] **Add `max_persons` field** to `StreamSchema` (default 1).
5. [ ] **Retire `stream_schema_builder.py`** — the freestanding `build_stream_schema()` is
      replaced by the classmethod. Move tests to test the classmethod instead.
6. [ ] **Wire the aggregator** — call `StreamSchema.from_standard_human()` at startup, cache
      the result where FMC-WS-2's encoder can access it.
7. [ ] **Update builder tests** — same coverage (channel count, rotation group kinds, bone
      names, hierarchy, RestPose) but called via the classmethod.

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
