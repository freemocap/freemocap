"""Reconstruct one sample with the same prepared tensor calculations as recordings."""
from collections.abc import Mapping
import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues
from skellyforge.core.data_tensors.data_tensor import _immutable_values
from freemocap.core.reconstruction.recording_pose_outputs import RecordingPoseOutputs
from freemocap.core.skeletons.reconstruction_state import SkeletonReconstructionState, FrozenModelScale
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction, ResidualValues, JointValues
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.types.channel_kind import ChannelKind


def reconstruct_skeleton(*, bundle: TrackedSkeletonBundle, state: SkeletonReconstructionState,
                         filtered_keypoints: Mapping[str, np.ndarray], compute_center_of_mass: bool) -> SkeletonReconstruction | None:
    mapped = state.map_frame(bundle=bundle, points=filtered_keypoints)
    if not mapped:
        return None
    poses = state.pose_geometry.recover_tensor(positions=mapped.data_values[None], landmark_present=mapped.entry_present[None])
    if not poses.segment_present.any():
        return SkeletonReconstruction(model_id=bundle.model_id, mapped_keypoints=mapped.immutable_copy())
    if state.roll_resolver is not None:
        poses = state.roll_resolver.resolve_tensor(poses=poses)
    reference_fit = (state.scale_source.current_tensor() if isinstance(state.scale_source, FrozenModelScale)
                     and state.scale_source.has_model_scale else state.diagnostic_reference_fit)
    state.scale_source.observe_tensor(poses=poses)
    fit = state.scale_source.current_tensor() if state.scale_source.has_model_scale else None
    state.diagnostic_reference_fit = fit
    if state.pose_outputs is None or state.pose_outputs.compute_center_of_mass != compute_center_of_mass:
        state.pose_outputs = RecordingPoseOutputs(bundle=bundle, fit=None, compute_center_of_mass=compute_center_of_mass)
    outputs = state.pose_outputs
    outputs.configure_fit(fit=fit, reference_fit=reference_fit,
                          reference_kind='recording_fit' if isinstance(state.scale_source, FrozenModelScale) else 'prior_live_fit')
    tensors = outputs.calculate(poses=poses, landmark_names=mapped.names,
        landmark_positions=mapped.data_values[None], landmark_present=mapped.entry_present[None], start_position=0)
    channels = {tensor.tensor_layout.channel_kind: tensor.immutable_copy() for tensor in tensors}

    def channel(kind):
        tensor = channels[kind]
        present = next(item.data_values[0] for item in tensor.companion_tensors if item.metadata_name == 'entry_presence')
        return ChannelValues(tensor.tensor_layout.axes[1].identifiers, tensor.data_values[0], _immutable_values(present.all(axis=-1)),
                             component_names=tensor.tensor_layout.axes[2].identifiers)

    residual = channels[ChannelKind.RIGID_BODY_RESIDUALS].data_values[0]
    angle_values = None
    if ChannelKind.JOINT_ANGLES in channels:
        angles = channel(ChannelKind.JOINT_ANGLES)
        angle_values = JointValues(angle_values=angles, definitions=outputs.joint_definitions)
    center = None
    if ChannelKind.DERIVED_POINTS in channels:
        center = channel(ChannelKind.DERIVED_POINTS).get('center_of_mass')
    return SkeletonReconstruction(model_id=bundle.model_id,
        mapped_keypoints=channel(ChannelKind.MAPPED_KEYPOINTS_3D),
        landmarks=channel(ChannelKind.LANDMARKS_3D), segment_origins=channel(ChannelKind.SEGMENT_ORIGINS),
        segment_rotations_world=channel(ChannelKind.ROTATIONS_WORLD), segment_rotations_local=channel(ChannelKind.ROTATIONS_LOCAL),
        segment_lengths=ChannelValues(fit.segment_names, fit.segment_lengths, component_names=()).immutable_copy() if fit else ChannelValues.empty(component_names=()),
        fitted_scale_mm=fit.fitted_scale if fit else None, joint_angles=angle_values, center_of_mass=center,
        rigid_body_residuals=ResidualValues(names=outputs.names, measured=residual[:, 0], residual=residual[:, 1],
            reference=outputs.residuals.reference_lengths.copy(), reference_kind=outputs.residuals.reference_kind))
