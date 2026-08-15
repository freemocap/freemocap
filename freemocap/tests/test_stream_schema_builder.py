"""FMC-WS-3 — producer-composed StreamSchema tests.

Builds the StandardHuman model (60 segments, 76 landmarks), composes
the schema through the channel producers, and verifies the nine channel groups
(KEYPOINTS_3D, LANDMARKS_3D, SEGMENT_ORIGINS, ROTATIONS_LOCAL, ROTATIONS_WORLD,
SEGMENT_LENGTHS, OVERLAY_2D, DERIVED_POINTS, IMAGE_JPEG), the hierarchy /
topology metadata, the anthropometric default lengths, round-trips through
JSON, and the LSL channel expansion. "Camera-only" vs "camera + reconstruction"
is two schemas produced by one mechanism — the producer activeness.
"""
import pytest

from freemocap.core.streaming.standard_stream import (
    FREEMOCAP_COORDINATE_CONVENTION,
    Axis,
    ChannelKind,
    OverlayLayer,
    decode_schema,
    encode_schema,
    schema_to_streaminfo_channels,
)
from freemocap.core.streaming.standard_stream.producers import compose
from freemocap.core.streaming.standard_stream.producers.producer_contexts import (
    StreamContext,
)
from freemocap.core.streaming.standard_stream.stream_schema import (
    NOMINAL_SUBJECT_HEIGHT_MM,
)
from skellyforge.skellymodels.standard_human.standard_human_model import (
    StandardHuman,
    compose_standard_human,
)

TRACKER_NAMES = ("left_hand_wrist", "nose", "right_shoulder")


def _minimal_model() -> StandardHuman:
    """The canonical 60-segment standard human."""
    return compose_standard_human()


def _context(**kwargs) -> StreamContext:
    kw = dict(
        standard_human=_minimal_model(),
        camera_ids=("cam-0", "cam-1"),
        tracker_keypoint_names=TRACKER_NAMES,
        pipeline_live=True,
    )
    kw.update(kwargs)
    return StreamContext(**kw)


def _schema(**kwargs):
    return compose(
        _context(**kwargs),
        stream_id="s1",
        stream_name="test",
    ).schema


# ── Channel group tests ────────────────────────────────────────────────


def test_schema_enumerates_ten_channel_groups():
    """The active producers contribute 10 channel groups in producer order."""
    channels = _schema().channels
    assert len(channels) == 10
    kinds = [group.kind for group in channels]
    assert kinds == [
        ChannelKind.KEYPOINTS_3D,
        ChannelKind.LANDMARKS_3D,
        ChannelKind.SEGMENT_ORIGINS,
        ChannelKind.ROTATIONS_LOCAL,
        ChannelKind.ROTATIONS_WORLD,
        ChannelKind.SEGMENT_LENGTHS,
        ChannelKind.OVERLAY_2D,
        ChannelKind.OVERLAY_REPROJECTIONS,
        ChannelKind.DERIVED_POINTS,
        ChannelKind.IMAGE_JPEG,
    ]


def test_camera_only_schema_has_image_group_only():
    """With no live pipeline, only the ImageProducer contributes."""
    channels = _schema(pipeline_live=False).channels
    assert [g.kind for g in channels] == [ChannelKind.IMAGE_JPEG]


def test_keypoints_3d_group():
    group = _schema().channels[0]
    assert group.kind == ChannelKind.KEYPOINTS_3D
    # The tracker-named measured keypoints, as passed by the context.
    assert group.names == TRACKER_NAMES
    assert group.columns == ("x", "y", "z", "reprojection_error")
    assert group.units == "mm"


def test_landmarks_3d_group():
    group = _schema().channels[1]
    assert group.kind == ChannelKind.LANDMARKS_3D
    # The 76 hydrated standard-human landmarks, sorted by name.
    assert group.names == tuple(sorted(_minimal_model().required_landmarks()))
    assert len(group.names) == 76
    assert group.columns == ("x", "y", "z", "reprojection_error")
    assert group.units == "mm"


def test_segment_origins_group():
    group = _schema().channels[2]
    assert group.kind == ChannelKind.SEGMENT_ORIGINS
    assert group.names == tuple(_minimal_model().segment_names)
    assert len(group.names) == 60
    assert group.columns == ("x", "y", "z")
    assert group.units == "mm"


def test_rotations_local_group():
    rlocal = _schema().channels[3]
    assert rlocal.kind == ChannelKind.ROTATIONS_LOCAL
    assert rlocal.names == tuple(_minimal_model().segment_names)
    assert rlocal.columns == ("w", "x", "y", "z")
    assert rlocal.units == "quaternion"


def test_rotations_world_group():
    rworld = _schema().channels[4]
    assert rworld.kind == ChannelKind.ROTATIONS_WORLD
    assert rworld.names == tuple(_minimal_model().segment_names)
    assert rworld.columns == ("w", "x", "y", "z")
    assert rworld.units == "quaternion"


def test_local_and_world_rotations_are_distinct():
    # Both rotation kinds are first-class and separate groups.
    rlocal = _schema().channels[3]
    rworld = _schema().channels[4]
    assert rlocal.kind is ChannelKind.ROTATIONS_LOCAL
    assert rworld.kind is ChannelKind.ROTATIONS_WORLD
    assert rlocal.kind != rworld.kind


def test_segment_lengths_group():
    lengths = _schema().channels[5]
    assert lengths.kind == ChannelKind.SEGMENT_LENGTHS
    assert lengths.names == tuple(_minimal_model().segment_names)
    assert lengths.columns == ("length_mm",)
    assert lengths.units == "mm"


def test_overlay_reprojections_group():
    reproj = _schema().channels[7]
    assert reproj.kind == ChannelKind.OVERLAY_REPROJECTIONS
    # Names are the 60 segment names — the fitted skeleton's origin landmarks
    # projected back into each camera.
    assert reproj.names == tuple(_minimal_model().segment_names)
    assert reproj.columns == ("x", "y", "visibility")
    assert reproj.units == "px"


def test_image_jpeg_group():
    image = _schema().channels[9]
    assert image.kind == ChannelKind.IMAGE_JPEG
    assert image.names == ("image",)
    assert image.columns == ("jpeg_bytes",)


def test_keypoints_vs_segments_split():
    # The measured half (keypoints) and the reconstructed half (segments) are two
    # distinct channel groups with distinct kinds. Their name sets may overlap
    # (e.g. `nose` is both a tracker keypoint and a face-segment name) — the
    # group kind, not the name, is what distinguishes the two on the wire.
    keypoints = _schema().channels[0]
    segments = _schema().channels[2]
    assert keypoints.kind is ChannelKind.KEYPOINTS_3D
    assert segments.kind is ChannelKind.SEGMENT_ORIGINS
    assert keypoints.kind != segments.kind
    assert len(keypoints.names) == 3
    assert len(segments.names) == 60


def test_derived_points_group():
    derived = _schema().channels[8]
    assert derived.kind == ChannelKind.DERIVED_POINTS
    assert derived.names == ("center_of_mass", "xcom")
    assert derived.columns == ("x", "y", "z")


def test_overlay_2d_group():
    overlay = _schema().channels[6]
    assert overlay.kind == ChannelKind.OVERLAY_2D
    # OVERLAY_2D names describe the DETECTIONS rows — the tracker-named 2D
    # detections (what the detector saw in each camera), not segment names.
    assert overlay.names == TRACKER_NAMES
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
    assert schema.coordinate_convention == FREEMOCAP_COORDINATE_CONVENTION
    assert schema.camera_ids == ("cam-0", "cam-1")
    assert schema.max_persons == 1


def test_schema_carries_capture_image_sizes():
    """camera_image_sizes pins the OVERLAY_2D coordinate space (capture-res px)."""
    assert _schema().camera_image_sizes == {}
    sizes = {"cam-0": (1920, 1080), "cam-1": (640, 480)}
    schema = _schema(camera_image_sizes=sizes)
    assert schema.camera_image_sizes == sizes
    # round-trips through JSON (tuples → arrays on the wire)
    assert decode_schema(encode_schema(schema)).camera_image_sizes == sizes


def test_convention_forward_axis_is_plus_x():
    # The coordinate convention is mm · right-handed · +Z up · +X forward.
    assert FREEMOCAP_COORDINATE_CONVENTION.forward_axis == Axis.PLUS_X
    assert FREEMOCAP_COORDINATE_CONVENTION.up_axis == Axis.PLUS_Z


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


# ── Segment-lengths tests ───────────────────────────────────────────────


def test_segment_lengths_default_to_ratio_times_height():
    """Every schema length is the anthropometric default; live estimates ride
    the per-frame SEGMENT_LENGTHS block, never the schema."""
    model = _minimal_model()
    schema = _schema()
    assert len(schema.segment_lengths) == 60
    for segment in model.segments:
        expected = segment.length_ratio * NOMINAL_SUBJECT_HEIGHT_MM
        assert schema.segment_lengths[segment.name] == expected


def test_camera_only_schema_carries_no_segment_lengths():
    """Without a live pipeline the SegmentProducer is inactive — no lengths."""
    schema = _schema(pipeline_live=False)
    assert schema.segment_lengths == {}
    assert schema.rest_pose is None
    assert schema.connections == ()


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
    assert set(rest.positions) == set(geometry.landmarks)
    for name, pos in geometry.landmarks.items():
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
    """LSL channel count covers all groups incl. per-camera overlays; the
    IMAGE_JPEG group is skipped (LSL is not a video consumer)."""
    channels = schema_to_streaminfo_channels(_schema())
    # keypoints_3d:    3 tracker keypoints × 4 cols = 12
    # landmarks_3d:   76 landmarks  × 4 cols = 304
    # segment_origins: 60 segments × 3 cols = 180
    # rotations_local: 60 segments × 4 cols = 240
    # rotations_world: 60 segments × 4 cols = 240
    # segment_lengths: 60 segments × 1 col  =  60
    # derived_points:   2 points   × 3 cols =   6
    # overlay_2d:       2 cams × 3 keypoints × 3 cols = 18
    # overlay_reproj:  60 segments × 3 cols = 180
    # total: 12 + 304 + 180 + 240 + 240 + 60 + 18 + 180 + 6 = 1240
    assert len(channels) == 1240


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
    # overlay names are the tracker keypoint names (the DETECTIONS rows).
    assert "cam-0.nose.x" in labels
    assert "cam-0.nose.y" in labels
    assert "cam-0.nose.visibility" in labels
    assert "cam-1.left_hand_wrist.x" in labels
    assert "cam-1.right_shoulder.visibility" in labels


def test_lsl_channels_carry_segment_lengths_but_not_images():
    channels = schema_to_streaminfo_channels(_schema())
    labels = [label for label, _unit in channels]
    assert "hips.length_mm" in labels
    assert not any(label.startswith("image.") for label in labels)
