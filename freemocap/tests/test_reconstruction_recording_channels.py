"""Missing local rotations, named angles and derived channels retain their semantics."""

import numpy as np
import pyarrow as pa

from freemocap.core.reconstruction.recording_reconstruction import (
    ModelRecordingReconstruction,
)
from freemocap.core.recording.channel_series import SeriesSampling
from freemocap.core.recording.reconstruction_recording import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.spatial_point_series import SpatialReference
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.types.channel_kind import ChannelKind


def test_partial_pose_preserves_world_orientation_and_missing_local_rotation() -> None:
    recording = ReconstructionRecording(
        sensor_group="mocap",
        reference=SpatialReference.for_camera_count(1),
        definition=ReconstructionSourceDefinition(
            model_id="subject",
            tracker="tracker",
            scale_reference_name="size",
            landmark_names=("origin", "tip"),
            segment_origins={"root": "origin", "child": "tip"},
            segment_parents={"root": None, "child": "root"},
            joint_angle_names={
                "joint": ("joint.flexion", "joint.abduction", "joint.rotation")
            },
        ),
        result=ModelRecordingReconstruction(
            compute_center_of_mass=True,
            scale_fit=None,
            frames=(
                SkeletonReconstruction(
                    model_id="subject",
                    segment_rotations_world={"child": np.array([1.0, 0.0, 0.0, 0.0])},
                    joint_angles={"joint": (0.1, 0.2, 0.3)},
                ),
            ),
        ),
    )
    series = {item.channel.kind: item for item in recording.series()}
    assert np.isnan(series[ChannelKind.ROTATIONS_LOCAL].values).all()
    assert (
        series[ChannelKind.ROTATIONS_LOCAL].channel.reference_frame
        == recording.parent_reference_name
    )
    assert series[ChannelKind.ROTATIONS_WORLD].values[0, 1, 0] == 1.0
    angles = series[ChannelKind.JOINT_ANGLES]
    assert angles.channel.names == (
        "joint.flexion",
        "joint.abduction",
        "joint.rotation",
    )
    assert list(angles.channel.components.values()) == ["rad"]
    assert angles.values.ravel().tolist() == [0.1, 0.2, 0.3]
    derived = series[ChannelKind.DERIVED_POINTS]
    assert derived.channel.names == ("center_of_mass",)
    assert set(derived.channel.components.values()) == {"px"}
    assert np.isnan(derived.values).all()
    batches = list(
        derived.batches(
            SeriesSampling(
                frame_numbers=(7,), timestamps_s=(0.25,), run_id=0, batch_size=2
            )
        )
    )
    assert [batch.num_rows for batch in batches] == [2, 1]
    assert pa.Table.from_batches(batches).column("value").null_count == 3
