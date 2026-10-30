"""Missing local rotations, named angles and derived channels retain their semantics."""

from dataclasses import replace

import numpy as np
import pytest
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
import pyarrow as pa

from freemocap.core.reconstruction.recording_reconstruction import (
    ModelRecordingReconstruction,
)
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionRecording,
    ReconstructionSourceDefinition,
)
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from skellyforge.core.data_tensors import AxisDefinition, DataTensor
from freemocap.core.reconstruction.recording_pose_outputs import reconstruction_tensor
from freemocap.core.types.channel_kind import ChannelKind


def test_partial_pose_preserves_world_orientation_and_missing_local_rotation() -> None:
    recording = ReconstructionRecording(
        sensor_group="mocap",
        reference=SpatialReference.for_camera_count(1),
        definition=ReconstructionSourceDefinition(
            point_kind=ChannelKind.RAW_KEYPOINTS_3D,
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
            fit_inputs=RecordingFitInputs(
                algorithm_version=1,
                keypoint_names=("point",),
                points="0" * 64,
                model="1" * 64,
            ),
            compute_center_of_mass=True,
            scale_fit=None,
            model_id="subject",
            channel_tensors=partial_pose_tensors(),
        ),
    )
    series = {item.channel.kind: item for item in recording.series()}
    for channel_kind, item in series.items():
        assert type(recording.result.channel_tensor(channel_kind)) is DataTensor
        assert item.values is recording.result.channel_tensor(channel_kind).data_values
        assert np.shares_memory(item.values, recording.result.channel_tensor(channel_kind).data_values)
        # Publication reads the existing channel array and allocates only bounded
        # Arrow columns; the immutable scientific tensor remains the owner.
        published = list(item.batches(SeriesSampling(
            frame_numbers=(7,), timestamps_s=(0.25,), run_id=4, batch_size=5)))
        assert all(batch.num_rows <= 5 for batch in published)
        values = pa.Table.from_batches(published).column('value').to_numpy()
        np.testing.assert_array_equal(values, item.values.reshape(-1))
        assert item.values is recording.result.channel_tensor(channel_kind).data_values
    assert not hasattr(recording.result, "frames")
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


def partial_pose_tensors():
    """Declare this synthetic fixture directly in the runtime tensor representation."""
    specifications = (
        (ChannelKind.MAPPED_KEYPOINTS_3D, ("origin", "tip"), ("x", "y", "z")),
        (ChannelKind.LANDMARKS_3D, ("origin", "tip"), ("x", "y", "z")),
        (ChannelKind.SEGMENT_ORIGINS, ("root", "child"), ("x", "y", "z")),
        (ChannelKind.ROTATIONS_WORLD, ("root", "child"), ("w", "x", "y", "z")),
        (ChannelKind.ROTATIONS_LOCAL, ("root", "child"), ("w", "x", "y", "z")),
        (ChannelKind.RIGID_BODY_RESIDUALS, ("root", "child"), ("measured_length", "residual")),
        (ChannelKind.JOINT_ANGLES, ("joint.flexion", "joint.abduction", "joint.rotation"), ("radians",)),
        (ChannelKind.DERIVED_POINTS, ("center_of_mass",), ("x", "y", "z")),
    )
    tensors = []
    for kind, names, components in specifications:
        values = np.full((1, len(names), len(components)), np.nan)
        if kind == ChannelKind.ROTATIONS_WORLD:
            values[0, 1] = (1., 0., 0., 0.)
        elif kind == ChannelKind.JOINT_ANGLES:
            values[0, :, 0] = (.1, .2, .3)
        tensors.append(reconstruction_tensor(model_id="subject", sample_positions=AxisDefinition("sample_position", (0,)),
            names=names, components=components, channel_kind=kind, values=values,
            entry_presence=np.isfinite(values)).immutable_copy())
    return tuple(tensors)


def test_recording_result_rejects_mutable_payload_and_invalid_layout():
    tensors = partial_pose_tensors()
    result = ModelRecordingReconstruction(
        fit_inputs=RecordingFitInputs(algorithm_version=1, keypoint_names=("point",), points="0"*64, model="1"*64),
        compute_center_of_mass=True, model_id="subject", channel_tensors=tensors, scale_fit=None)
    with pytest.raises(ValueError, match="immutable"):
        replace(result, channel_tensors=(tensors[0].mutable_copy(), *tensors[1:]))
    invalid = replace(tensors[0], data_values=np.asarray(np.nan),
        tensor_layout=replace(tensors[0].tensor_layout, axes=()), companion_tensors=()).immutable_copy()
    with pytest.raises(ValueError, match="axes"):
        replace(result, channel_tensors=(invalid,))
    invalid = replace(tensors[0], tensor_layout=replace(tensors[0].tensor_layout, channel_kind=None)).immutable_copy()
    with pytest.raises(ValueError, match="channel kind"):
        replace(result, channel_tensors=(invalid,))
    invalid = replace(tensors[0], tensor_layout=replace(tensors[0].tensor_layout, source_identity=None)).immutable_copy()
    with pytest.raises(ValueError, match="model source"):
        replace(result, channel_tensors=(invalid,))
    with pytest.raises(ValueError, match="model ID"):
        replace(result, model_id="")
