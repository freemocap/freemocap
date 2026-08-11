"""WS-3 — the standard-stream schema builder (canonical model → StreamSchema).

Pure builder tests (no pipeline / SkellyForge): it declares the right channel
groups, carries the topology (convention / hierarchy / cameras), round-trips
through JSON, and expands OVERLAY_2D per camera in the LSL channel list.
"""
from freemocap.core.streaming.standard_stream import (
    FREEMOCAP_CANONICAL_CONVENTION,
    ChannelKind,
    build_stream_schema,
    decode_schema,
    encode_schema,
    schema_to_streaminfo_channels,
)


def _schema():
    return build_stream_schema(
        stream_id="s1",
        stream_name="test",
        landmark_names=("left_elbow", "right_elbow"),
        segment_names=("left_upper_arm",),
        connections=(("left_shoulder", "left_elbow"),),
        joint_hierarchy={"left_shoulder": ("left_elbow",)},
        camera_ids=("cam-0", "cam-1"),
    )


def test_builder_declares_expected_groups():
    skeleton, derived, rotations, overlay = _schema().channels
    assert [skeleton.kind, derived.kind, rotations.kind, overlay.kind] == [
        ChannelKind.POINTS, ChannelKind.POINTS, ChannelKind.ROTATIONS, ChannelKind.OVERLAY_2D,
    ]
    assert skeleton.names == ("left_elbow", "right_elbow")
    assert skeleton.columns == ("x", "y", "z", "reprojection_error")
    assert derived.names == ("center_of_mass", "xcom")
    assert derived.columns == ("x", "y", "z")  # derived points carry no reprojection error
    assert rotations.names == ("left_upper_arm",)
    assert rotations.columns == ("w", "x", "y", "z")
    assert overlay.names == ("left_elbow", "right_elbow")
    assert overlay.columns == ("x", "y", "visibility")
    assert overlay.units == "px"


def test_builder_carries_topology():
    schema = _schema()
    assert schema.coordinate_convention == FREEMOCAP_CANONICAL_CONVENTION
    assert schema.joint_hierarchy["left_shoulder"] == ("left_elbow",)
    assert schema.camera_ids == ("cam-0", "cam-1")


def test_built_schema_roundtrips():
    schema = _schema()
    assert decode_schema(encode_schema(schema)) == schema


def test_lsl_channels_expand_overlays_per_camera():
    channels = schema_to_streaminfo_channels(_schema())
    # skeleton 2×4=8, derived 2×3=6, rotations 1×4=4, overlays 2 cams × 2 lm × 3 = 12  → 30
    assert len(channels) == 30
    labels = [label for label, _unit in channels]
    assert "left_elbow.reprojection_error" in labels
    assert "center_of_mass.x" in labels
    assert "cam-0.left_elbow.x" in labels
    assert "cam-1.right_elbow.visibility" in labels
