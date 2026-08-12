"""FMC-WS-3 — StreamSchema.from_standard_human() classmethod tests.

Builds a minimal StandardHuman model and verifies the schema enumerates the
correct channel groups (SKELETON_POINTS, DERIVED_POINTS, ROTATIONS_WORLD,
ROTATIONS_LOCAL, OVERLAY_2D), carries topology, round-trips through JSON,
and expands OVERLAY_2D per camera in the LSL channel list.
"""
from freemocap.core.streaming.standard_stream import (
    FREEMOCAP_CANONICAL_CONVENTION,
    ChannelKind,
    StreamSchema,
    decode_schema,
    encode_schema,
    schema_to_streaminfo_channels,
)
from skellyforge.skellymodels.standard_human.standard_human_model import StandardHuman


def _minimal_model() -> StandardHuman:
    """A 3-bone skeleton: hips → spine → head. Enough to exercise every channel group."""
    return StandardHuman.from_bone_definitions(
        name="test_human",
        bone_defs=[
            {
                "name": "hips",
                "parent": None,
                "required": True,
                "proximal_joint": [0.0, 0.0, 900.0],
                "distal_joint": [0.0, 0.0, 1050.0],
                "exact_axis": [0.0, 0.0, 1.0],
                "approximate_axis": [0.0, 1.0, 0.0],
                "twist_tier": "full_frame",
            },
            {
                "name": "spine",
                "parent": "hips",
                "required": True,
                "proximal_joint": [0.0, 0.0, 1050.0],
                "distal_joint": [0.0, 0.0, 1350.0],
                "exact_axis": [0.0, 0.0, 1.0],
                "approximate_axis": [0.0, 1.0, 0.0],
                "twist_tier": "chain_resolved",
                "twist_source_bone": "head",
            },
            {
                "name": "head",
                "parent": "spine",
                "required": True,
                "proximal_joint": [0.0, 0.0, 1350.0],
                "distal_joint": [0.0, 0.0, 1500.0],
                "exact_axis": [0.0, 0.0, 1.0],
                "approximate_axis": [0.0, 1.0, 0.0],
                "twist_tier": "full_frame",
            },
        ],
    )


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
    assert skeleton.names == ("hips", "spine", "head")
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
    assert rworld.names == ("hips", "spine", "head")
    assert rworld.columns == ("w", "x", "y", "z")
    assert rworld.units == "quaternion"


def test_rotations_local_group():
    rlocal = _schema().channels[3]
    assert rlocal.kind == ChannelKind.ROTATIONS_LOCAL
    assert rlocal.names == ("hips", "spine", "head")
    assert rlocal.columns == ("w", "x", "y", "z")


def test_overlay_2d_group():
    overlay = _schema().channels[4]
    assert overlay.kind == ChannelKind.OVERLAY_2D
    assert overlay.names == ("hips", "spine", "head")
    assert overlay.columns == ("x", "y", "visibility")
    assert overlay.units == "px"


# ── Topology tests ──────────────────────────────────────────────────────


def test_schema_carries_topology():
    schema = _schema()
    assert schema.coordinate_convention == FREEMOCAP_CANONICAL_CONVENTION
    assert schema.camera_ids == ("cam-0", "cam-1")
    assert schema.max_persons == 1


def test_connections_from_hierarchy():
    """Parent→child bone edges match the model's hierarchy."""
    connections = _schema().connections
    # hips→spine, spine→head
    assert ("hips", "spine") in connections
    assert ("spine", "head") in connections
    assert len(connections) == 2


def test_joint_hierarchy_from_model():
    hierarchy = _schema().joint_hierarchy
    # model.joint_hierarchy uses __root__ key for the root bone's children
    assert "hips" in hierarchy["__root__"]
    assert "spine" in hierarchy["hips"]
    assert "head" in hierarchy["spine"]


# ── Rest pose tests ─────────────────────────────────────────────────────


def test_rest_pose_positions():
    rest = _schema().rest_pose
    assert rest is not None
    assert len(rest.positions) == 3  # hips, spine, head
    # hips proximal joint center should be at (0, 0, 900)
    assert rest.positions["hips"] == (0.0, 0.0, 900.0)
    assert rest.positions["spine"] == (0.0, 0.0, 1050.0)
    assert rest.positions["head"] == (0.0, 0.0, 1350.0)


def test_rest_pose_orientations_are_identity():
    rest = _schema().rest_pose
    identity = (1.0, 0.0, 0.0, 0.0)
    assert rest is not None
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
    # skeleton:  3 bones × 4 cols = 12
    # derived:   2 points × 3 cols = 6
    # rworld:    3 bones × 4 cols = 12
    # rlocal:    3 bones × 4 cols = 12
    # overlay:   2 cams × 3 bones × 3 cols = 18
    # total: 60
    assert len(channels) == 60


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
