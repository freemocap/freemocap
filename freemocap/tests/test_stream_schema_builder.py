"""FMC-WS-3 — StreamSchema.from_standard_human() classmethod tests.

Builds the canonical StandardHuman model (60 segments) and verifies the schema
enumerates the correct channel groups (SKELETON_POINTS, DERIVED_POINTS,
ROTATIONS_WORLD, ROTATIONS_LOCAL, OVERLAY_2D), carries topology, round-trips
through JSON, and expands OVERLAY_2D per camera in the LSL channel list.
"""
from freemocap.core.streaming.standard_stream import (
    FREEMOCAP_CANONICAL_CONVENTION,
    ChannelKind,
    StreamSchema,
    decode_schema,
    encode_schema,
    schema_to_streaminfo_channels,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,
    compose_standard_human,
)


def _minimal_model() -> StandardHuman:
    """The canonical 60-segment standard human."""
    return compose_standard_human()


def _schema():
    return StreamSchema.from_standard_human(
        stream_id="s1",
        stream_name="test",
        standard_human=_minimal_model(),
        camera_ids=("cam-0", "cam-1"),
    )


# ── Channel group tests ────────────────────────────────────────────────


def test_schema_enumerates_five_channel_groups():
    """from_standard_human produces 5 channel groups in the fixed order."""
    channels = _schema().channels
    assert len(channels) == 5
    skeleton, derived, rworld, rlocal, overlay = channels
    kinds = [skeleton.kind, derived.kind, rworld.kind, rlocal.kind, overlay.kind]
    assert kinds == [
        ChannelKind.POINTS,
        ChannelKind.POINTS,
        ChannelKind.ROTATIONS_WORLD,
        ChannelKind.ROTATIONS_LOCAL,
        ChannelKind.OVERLAY_2D,
    ]


def test_skeleton_points_group():
    skeleton = _schema().channels[0]
    assert skeleton.kind == ChannelKind.POINTS
    assert skeleton.names == tuple(_minimal_model().segment_names)
    assert skeleton.columns == ("x", "y", "z", "reprojection_error")
    assert skeleton.units == "mm"


def test_derived_points_group():
    derived = _schema().channels[1]
    assert derived.kind == ChannelKind.POINTS
    assert derived.names == ("center_of_mass", "xcom")
    assert derived.columns == ("x", "y", "z")


def test_rotations_world_group():
    rworld = _schema().channels[2]
    assert rworld.kind == ChannelKind.ROTATIONS_WORLD
    assert rworld.names == tuple(_minimal_model().segment_names)
    assert rworld.columns == ("w", "x", "y", "z")
    assert rworld.units == "quaternion"


def test_rotations_local_group():
    rlocal = _schema().channels[3]
    assert rlocal.kind == ChannelKind.ROTATIONS_LOCAL
    assert rlocal.names == tuple(_minimal_model().segment_names)
    assert rlocal.columns == ("w", "x", "y", "z")


def test_overlay_2d_group():
    overlay = _schema().channels[4]
    assert overlay.kind == ChannelKind.OVERLAY_2D
    assert overlay.names == tuple(_minimal_model().segment_names)
    assert overlay.columns == ("x", "y", "visibility")
    assert overlay.units == "px"


# ── Topology tests ──────────────────────────────────────────────────────


def test_schema_carries_topology():
    schema = _schema()
    assert schema.coordinate_convention == FREEMOCAP_CANONICAL_CONVENTION
    assert schema.camera_ids == ("cam-0", "cam-1")
    assert schema.max_persons == 1


def test_connections_from_hierarchy():
    """Parent→child segment edges match the model's hierarchy."""
    connections = _schema().connections
    # hips→spine, spine→head (and the 60-segment model's full edge set)
    assert ("hips", "spine") in connections
    assert ("spine", "chest") in connections
    assert ("hips", "left_upper_leg") in connections
    # 60 segments, 1 root — so 59 parent→child edges
    assert len(connections) == 59


def test_joint_hierarchy_from_model():
    hierarchy = _schema().joint_hierarchy
    # model.joint_hierarchy is {parent: [child names]}; the root ('hips') is a
    # key (its children), there is no '__root__' sentinel.
    assert "spine" in hierarchy["hips"]
    assert "left_upper_leg" in hierarchy["hips"]
    assert "chest" in hierarchy["spine"]
    assert "head" in hierarchy["neck"]


# ── Rest pose tests ─────────────────────────────────────────────────────


def test_rest_pose_positions():
    rest = _schema().rest_pose
    assert rest is not None
    # the reference geometry emits one rest position per declared keypoint (71
    # for the 60-segment human), not per segment.
    assert len(rest.positions) == 71
    # the root segment's origin keypoint sits at the model origin.
    assert rest.positions["hips_center"] == (0.0, 0.0, 0.0)


def test_rest_pose_orientations_are_identity():
    rest = _schema().rest_pose
    identity = (1.0, 0.0, 0.0, 0.0)
    assert rest is not None
    # one identity orientation per segment name
    assert len(rest.reference_orientations) == len(_minimal_model().segments)
    for name in ("hips", "spine", "head"):
        assert rest.reference_orientations[name] == identity


# ── Round-trip tests ────────────────────────────────────────────────────


def test_schema_json_roundtrip():
    """Schema survives encode→decode unchanged."""
    schema = _schema()
    assert decode_schema(encode_schema(schema)) == schema


# ── LSL bridge tests ────────────────────────────────────────────────────


def test_lsl_channels_count():
    """LSL channel count covers all groups including per-camera overlays."""
    channels = schema_to_streaminfo_channels(_schema())
    # skeleton: 60 segments × 4 cols = 240
    # derived:   2 points × 3 cols = 6
    # rworld:   60 segments × 4 cols = 240
    # rlocal:   60 segments × 4 cols = 240
    # overlay:   2 cams × 60 segments × 3 cols = 360
    # total: 1086
    assert len(channels) == 1086


def test_lsl_channels_have_rotation_labels():
    channels = schema_to_streaminfo_channels(_schema())
    labels = [label for label, _unit in channels]
    assert "hips.w" in labels
    assert "spine.x" in labels
    assert "head.y" in labels
    assert "head.z" in labels


def test_lsl_channels_expand_overlays_per_camera():
    channels = schema_to_streaminfo_channels(_schema())
    labels = [label for label, _unit in channels]
    assert "cam-0.hips.x" in labels
    assert "cam-0.hips.y" in labels
    assert "cam-0.hips.visibility" in labels
    assert "cam-1.spine.x" in labels
    assert "cam-1.head.visibility" in labels
