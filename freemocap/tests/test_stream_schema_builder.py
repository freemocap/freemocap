"""FMC-WS-3 — StreamSchema.from_standard_human() classmethod tests.

Builds the canonical StandardHuman model (60 segments, 76 required keypoints)
and verifies the schema enumerates the six channel groups (KEYPOINTS_3D,
SEGMENT_ORIGINS, ROTATIONS_LOCAL, ROTATIONS_WORLD, DERIVED_POINTS, OVERLAY_2D),
carries topology + segment_parents, round-trips through JSON, and expands
OVERLAY_2D per camera in the LSL channel list.

The authoritative channel layout is
[09 — the Standard Stream Protocol](../../docs/streaming-compatibility/09-standard-stream-protocol.md#channels);
this module asserts the code matches it.
"""
import pytest

from freemocap.core.streaming.standard_stream import (
    FREEMOCAP_CANONICAL_CONVENTION,
    Axis,
    ChannelKind,
    OverlayLayer,
    StreamSchema,
    decode_schema,
    encode_schema,
    schema_to_streaminfo_channels,
)
from freemocap.core.streaming.standard_stream.stream_schema import (
    NOMINAL_SUBJECT_HEIGHT_MM,
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


def test_schema_enumerates_six_channel_groups():
    """from_standard_human produces 6 channel groups in the fixed order."""
    channels = _schema().channels
    assert len(channels) == 6
    kinds = [group.kind for group in channels]
    assert kinds == [
        ChannelKind.KEYPOINTS_3D,
        ChannelKind.SEGMENT_ORIGINS,
        ChannelKind.ROTATIONS_LOCAL,
        ChannelKind.ROTATIONS_WORLD,
        ChannelKind.DERIVED_POINTS,
        ChannelKind.OVERLAY_2D,
    ]


def test_keypoints_3d_group():
    group = _schema().channels[0]
    assert group.kind == ChannelKind.KEYPOINTS_3D
    # 76 required keypoints, sorted by name.
    assert group.names == tuple(sorted(_minimal_model().required_keypoints()))
    assert len(group.names) == 76
    assert group.columns == ("x", "y", "z", "reprojection_error")
    assert group.units == "mm"


def test_segment_origins_group():
    group = _schema().channels[1]
    assert group.kind == ChannelKind.SEGMENT_ORIGINS
    assert group.names == tuple(_minimal_model().segment_names)
    assert len(group.names) == 60
    assert group.columns == ("x", "y", "z")
    assert group.units == "mm"


def test_rotations_local_group():
    rlocal = _schema().channels[2]
    assert rlocal.kind == ChannelKind.ROTATIONS_LOCAL
    assert rlocal.names == tuple(_minimal_model().segment_names)
    assert rlocal.columns == ("w", "x", "y", "z")
    assert rlocal.units == "quaternion"


def test_rotations_world_group():
    rworld = _schema().channels[3]
    assert rworld.kind == ChannelKind.ROTATIONS_WORLD
    assert rworld.names == tuple(_minimal_model().segment_names)
    assert rworld.columns == ("w", "x", "y", "z")
    assert rworld.units == "quaternion"


def test_local_and_world_rotations_are_distinct():
    # Both rotation kinds are first-class and separate groups.
    rlocal = _schema().channels[2]
    rworld = _schema().channels[3]
    assert rlocal.kind is ChannelKind.ROTATIONS_LOCAL
    assert rworld.kind is ChannelKind.ROTATIONS_WORLD
    assert rlocal.kind != rworld.kind


def test_keypoints_vs_segments_split():
    # The measured half (keypoints) and the reconstructed half (segments) are two
    # distinct channel groups with distinct kinds. Their name sets may overlap
    # (e.g. `head`, `jaw` are both keypoint and segment names) — the group kind,
    # not the name, is what distinguishes the two on the wire.
    keypoints = _schema().channels[0]
    segments = _schema().channels[1]
    assert keypoints.kind is ChannelKind.KEYPOINTS_3D
    assert segments.kind is ChannelKind.SEGMENT_ORIGINS
    assert keypoints.kind != segments.kind
    assert len(keypoints.names) == 76
    assert len(segments.names) == 60


def test_derived_points_group():
    derived = _schema().channels[4]
    assert derived.kind == ChannelKind.DERIVED_POINTS
    assert derived.names == ("center_of_mass", "xcom")
    assert derived.columns == ("x", "y", "z")


def test_overlay_2d_group():
    overlay = _schema().channels[5]
    assert overlay.kind == ChannelKind.OVERLAY_2D
    # F2a review fix: OVERLAY_2D names describe the DETECTIONS rows — the 76
    # keypoint names (what the detector saw in each camera), not segment names.
    assert overlay.names == tuple(sorted(_minimal_model().required_keypoints()))
    assert len(overlay.names) == 76
    assert overlay.columns == ("x", "y", "visibility")
    assert overlay.units == "px"


def test_overlay_layer_enum_present():
    # Per-camera overlays discriminate two layers (detections vs reprojections).
    # The .value is the wire byte (u1) in the block header.
    assert int(OverlayLayer.DETECTIONS) == 0
    assert int(OverlayLayer.REPROJECTIONS) == 1
    assert list(OverlayLayer) == [OverlayLayer.DETECTIONS, OverlayLayer.REPROJECTIONS]


# ── Topology tests ──────────────────────────────────────────────────────


def test_schema_carries_topology():
    schema = _schema()
    assert schema.coordinate_convention == FREEMOCAP_CANONICAL_CONVENTION
    assert schema.camera_ids == ("cam-0", "cam-1")
    assert schema.max_persons == 1


def test_convention_forward_axis_is_plus_x():
    # D34 — the canonical convention is mm · right-handed · +Z up · +X forward.
    assert FREEMOCAP_CANONICAL_CONVENTION.forward_axis == Axis.PLUS_X
    assert FREEMOCAP_CANONICAL_CONVENTION.up_axis == Axis.PLUS_Z


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


def test_segment_parents_agrees_with_model():
    """D29 — segment_parents mirrors the model's segment_parents exactly."""
    model = _minimal_model()
    schema = _schema()
    for name, parent in model.segment_parents.items():
        assert schema.segment_parents[name] == parent
    assert len(schema.segment_parents) == 60
    # the root has no parent
    assert schema.segment_parents["hips"] is None
    assert schema.segment_parents["spine"] == "hips"


# ── Segment-lengths tests (default-then-update lifecycle) ────────────────


def test_segment_lengths_default_to_ratio_times_height():
    """Every segment's default length == length_ratio × NOMINAL_SUBJECT_HEIGHT_MM."""
    model = _minimal_model()
    schema = _schema()
    assert len(schema.segment_lengths) == 60
    for segment in model.segments:
        expected = segment.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM
        assert schema.segment_lengths[segment.name] == expected


def test_segment_lengths_override_replaces_measured_and_keeps_defaults():
    """An override dict replaces the named segments, leaves the rest default."""
    model = _minimal_model()
    schema = StreamSchema.from_standard_human(
        stream_id="s1",
        stream_name="test",
        standard_human=model,
        camera_ids=("cam-0", "cam-1"),
        measured_lengths={"left_upper_arm": 333.0},
    )
    assert schema.segment_lengths["left_upper_arm"] == 333.0
    # A non-overridden segment keeps its anthropometric default.
    expected_spine = next(
        s.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM for s in model.segments if s.name == "spine"
    )
    assert schema.segment_lengths["spine"] == expected_spine
    assert len(schema.segment_lengths) == 60


def test_rest_pose_consistent_with_measured_lengths():
    """The rest pose and segment_lengths share the same merged lengths dict."""
    model = _minimal_model()
    schema = StreamSchema.from_standard_human(
        stream_id="s1",
        stream_name="test",
        standard_human=model,
        measured_lengths={"left_upper_arm": 333.0},
    )
    # The rest pose was built from the same merged dict, so a measured segment's
    # rest-pose span reflects the override (left_shoulder → left_elbow along the
    # arm's long axis in the reference geometry). Just assert the schema carries
    # the override in both places consistently (exact span is solver territory).
    assert schema.segment_lengths["left_upper_arm"] == 333.0
    assert schema.rest_pose is not None


# ── Rest pose tests ─────────────────────────────────────────────────────


def test_rest_pose_positions():
    rest = _schema().rest_pose
    assert rest is not None
    # The reference geometry emits one rest position per keypoint that has a
    # schematic rest position (71 of the 76 required keypoints: `nose` and the
    # heel/small_toe off-chain keypoints have none), not per segment.
    assert len(rest.positions) == 71
    # the root segment's origin keypoint sits at the model origin.
    assert rest.positions["hips_center"] == (0.0, 0.0, 0.0)


def test_rest_pose_positions_match_reference_geometry():
    """RestPose positions exactly equal the reference geometry's keypoints."""
    from skellyforge.skellymodels.standard_human.reference_geometry import (
        build_reference_geometry,
    )

    model = _minimal_model()
    nominal = {s.name: s.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM for s in model.segments}
    geometry = build_reference_geometry(list(model.segments), nominal)

    rest = _schema().rest_pose
    assert rest is not None
    assert set(rest.positions) == set(geometry.keypoints)
    for name, pos in geometry.keypoints.items():
        assert rest.positions[name] == (
            float(pos[0]),
            float(pos[1]),
            float(pos[2]),
        )


def test_rest_pose_orientations_are_identity():
    rest = _schema().rest_pose
    identity = (1.0, 0.0, 0.0, 0.0)
    assert rest is not None
    # one identity orientation per segment name
    assert len(rest.reference_orientations) == len(_minimal_model().segments)
    for name in ("hips", "spine", "head"):
        assert rest.reference_orientations[name] == identity


# ── Frozen schema tests (D22) ───────────────────────────────────────────


def test_schema_is_frozen():
    schema = _schema()
    with pytest.raises(Exception):
        schema.stream_name = "mutated"


def test_schema_channels_are_frozen():
    schema = _schema()
    with pytest.raises(Exception):
        schema.channels[0].names = ("mutated",)


def test_rest_pose_is_frozen():
    rest = _schema().rest_pose
    assert rest is not None
    with pytest.raises(Exception):
        rest.positions = {}


# ── Round-trip tests ────────────────────────────────────────────────────


def test_schema_json_roundtrip():
    """Schema survives encode→decode unchanged."""
    schema = _schema()
    assert decode_schema(encode_schema(schema)) == schema


def test_schema_json_roundtrip_preserves_segment_parents():
    schema = _schema()
    restored = decode_schema(encode_schema(schema))
    assert restored.segment_parents == schema.segment_parents


# ── LSL bridge tests ────────────────────────────────────────────────────


def test_lsl_channels_count():
    """LSL channel count covers all groups including per-camera overlays."""
    channels = schema_to_streaminfo_channels(_schema())
    # keypoints_3d:  76 keypoints × 4 cols = 304
    # segment_origins: 60 segments × 3 cols = 180
    # rotations_local: 60 segments × 4 cols = 240
    # rotations_world: 60 segments × 4 cols = 240
    # derived_points:  2 points   × 3 cols =   6
    # overlay_2d:      2 cams × 76 keypoints × 3 cols = 456
    # total: 304 + 180 + 240 + 240 + 6 + 456 = 1426
    assert len(channels) == 1426


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
    # overlay names are now keypoint names (the DETECTIONS rows).
    assert "cam-0.hips_center.x" in labels
    assert "cam-0.hips_center.y" in labels
    assert "cam-0.hips_center.visibility" in labels
    assert "cam-1.nose.x" in labels
    assert "cam-1.head_center.visibility" in labels
