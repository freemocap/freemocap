"""Compose Forge batch calculations and retain numerical recording channels."""
import numpy as np
from skellyforge.core.biomechanics.center_of_mass_batch import CenterOfMassGeometry
from skellyforge.core.math.geometry.rotation_quaternion import (
    conjugate_quaternion_array, hamilton_product, normalize_quaternion_array,
)
from skellyforge.core.skeleton.chain.anchored_batch import AnchoredSkeletonGeometry
from skellyforge.core.skeleton.linkage.joint_batch import JointBatchGeometry
from skellyforge.core.skeleton.pose.hydration_batch import HydratedPoseBatch
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit, scale_voting_segment_names
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import ResidualBatchGeometry

from freemocap.core.data_tensors import (
    AxisDefinition, CompanionTensor, DataTensor, ScientificProvenance, SourceIdentity, TensorLayout,
)
from freemocap.core.skeletons.rotation_output import canonical_joint_angle_array, canonical_quaternion_array
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle
from freemocap.core.types.channel_kind import ChannelKind

POSITION_COMPONENTS = ("x", "y", "z")
ROTATION_COMPONENTS = ("w", "x", "y", "z")


def reconstruction_tensor(*, model_id: str, sample_positions: AxisDefinition, names: tuple[str, ...],
                          components: tuple[str, ...], channel_kind: str, values: np.ndarray,
                          entry_presence: np.ndarray, solver_status: np.ndarray | None = None) -> DataTensor:
    """Bind declared channel axes; physical units/reference are supplied when saving."""
    from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
    axes = (sample_positions, AxisDefinition("entity_identity", names), AxisDefinition("component_identity", components))
    source = SourceIdentity(source_id=model_source_name(model_id), model_id=model_id)
    layout = TensorLayout(axes=axes, dtype=np.float64, source_identity=source, channel_kind=str(channel_kind))
    companions = [CompanionTensor("entry_presence", entry_presence, TensorLayout(axes=axes, dtype=bool))]
    if solver_status is not None:
        companions.append(CompanionTensor("solver_status", solver_status, TensorLayout(axes=axes[:-1], dtype=solver_status.dtype)))
    return DataTensor(values, layout, ScientificProvenance("model_estimate", "recording_reconstruction", model_id=model_id),
                      tuple(companions))


class RecordingPoseOutputs:
    """Prepared geometry and named selections shared by all recording chunks."""

    def __init__(self, *, bundle: TrackedSkeletonBundle, fit: ModelScaleFit | None,
                 compute_center_of_mass: bool):
        self.bundle = bundle
        self.fit = fit
        self.names = tuple(bundle.skeleton.segments)
        self.landmark_names = tuple(bundle.skeleton.landmarks)
        self.indices = {name: i for i, name in enumerate(self.names)}
        self.landmark_indices = {name: i for i, name in enumerate(self.landmark_names)}
        self.parents = np.array([self.indices.get(bundle.rest_pose.parents[n], self.indices[n]) for n in self.names])
        self.roots = np.array([bundle.rest_pose.parents[n] is None for n in self.names])
        self.positions = AnchoredSkeletonGeometry.from_skeleton(skeleton=bundle.skeleton,
            fit=fit, anchor_segment_name=bundle.anchor_segment_name or bundle.rest_pose.root_segment_name) if fit else None
        self.joints = JointBatchGeometry.from_skeleton(skeleton=bundle.skeleton)
        self.residuals = ResidualBatchGeometry.from_skeleton(skeleton=bundle.skeleton,
            measured_segment_names=frozenset(scale_voting_segment_names(skeleton=bundle.skeleton,
                measured_landmark_names=bundle.landmark_mapping.directly_measured_landmark_names)),
            reference_lengths=fit.segment_lengths if fit else {}, reference_kind='recording_fit')
        self.compute_center_of_mass = compute_center_of_mass
        self.center = CenterOfMassGeometry.from_definitions(definitions=bundle.center_of_mass_definitions,
            landmark_names=self.positions.landmark_names, segment_masses=bundle.segment_masses
        ) if compute_center_of_mass and self.positions and bundle.center_of_mass_definitions.definitions else None
        self._mapping_columns: dict[tuple[str, ...], np.ndarray] = {}
        self._connected_columns = np.asarray([self.landmark_indices[name] for name in self.positions.landmark_names]) if self.positions else None

    def calculate(self, *, poses: HydratedPoseBatch, landmark_names: tuple[str, ...],
                  landmark_positions: np.ndarray, landmark_present: np.ndarray, start_position: int) -> tuple[DataTensor, ...]:
        """Calculate entire chunks; no per-frame result objects or numerical dictionaries."""
        rotations, origins, scales = poses.orientations, poses.origins, poses.scale_estimates
        present = poses.segment_present
        frame_count = len(rotations)
        measured, residuals = self.residuals.calculate(scales=scales, segment_present=present)
        joints = self.joints.calculate(world_orientations=rotations, segment_present=present, segment_solutions=poses.solutions)
        selected = np.zeros_like(present)
        connected = None
        if self.positions:
            selected[:, self.positions.anchor_index] = present[:, self.positions.anchor_index]
            # Tree dependencies require depth order; frames and branches batch together.
            for parents, children, _, _ in self.positions.traversal_levels:
                selected[:, children] = selected[:, parents] & present[:, children]
            connected = self.positions.positions(world_orientations=rotations, segment_present=selected,
                anchor_origins=origins[:, self.positions.anchor_index])
        local_present = selected & present[:, self.parents]
        local = np.full_like(rotations, np.nan)
        local[local_present] = normalize_quaternion_array(quaternions=hamilton_product(
            left=conjugate_quaternion_array(quaternions=rotations[:, self.parents][local_present]),
            right=rotations[local_present]))
        local[:, self.roots] = rotations[:, self.roots]
        center = self.center.calculate(positions=connected.landmark_positions,
            landmark_present=connected.landmark_present) if self.center else None
        joint_selected = selected[:, self.joints.parent_indices] & selected[:, self.joints.child_indices]
        sample_axis = AxisDefinition("sample_position", range(start_position, start_position + frame_count))
        tensors = []

        def retain(kind, names, components, values, available, status=None):
            presence = np.broadcast_to(available[..., None], values.shape) if available.ndim == values.ndim - 1 else available
            tensors.append(reconstruction_tensor(model_id=self.bundle.model_id, sample_positions=sample_axis,
                names=names, components=components, channel_kind=kind, values=values,
                entry_presence=presence, solver_status=status))

        mapped_values = np.full((frame_count, len(self.landmark_names), len(POSITION_COMPONENTS)), np.nan)
        mapped_presence = np.zeros(mapped_values.shape[:-1], dtype=bool)
        columns = self._mapping_columns.get(landmark_names)
        if columns is None:
            if len(set(landmark_names)) != len(landmark_names) or not set(landmark_names).issubset(self.landmark_indices):
                raise ValueError("Mapped landmarks must be unique declared model landmarks")
            columns = np.asarray([self.landmark_indices[name] for name in landmark_names], dtype=np.int64)
            self._mapping_columns[landmark_names] = columns
        mapped_values[:, columns] = np.where(landmark_present[..., None], landmark_positions, np.nan)
        mapped_presence[:, columns] = landmark_present
        retain(ChannelKind.MAPPED_KEYPOINTS_3D, self.landmark_names, POSITION_COMPONENTS, mapped_values, mapped_presence)
        model_values = np.full_like(mapped_values, np.nan)
        model_presence = np.zeros_like(mapped_presence)
        if connected is not None:
            model_values[:, self._connected_columns] = np.where(connected.landmark_present[..., None], connected.landmark_positions, np.nan)
            model_presence[:, self._connected_columns] = connected.landmark_present
        retain(ChannelKind.LANDMARKS_3D, self.landmark_names, POSITION_COMPONENTS, model_values, model_presence)
        connected_origins = np.where(selected[..., None], connected.segment_origins, np.nan) if connected else np.full_like(origins, np.nan)
        retain(ChannelKind.SEGMENT_ORIGINS, self.names, POSITION_COMPONENTS, connected_origins, selected, poses.status)
        world_values = np.full_like(rotations, np.nan)
        world_values[selected] = canonical_quaternion_array(rotations[selected])
        retain(ChannelKind.ROTATIONS_WORLD, self.names, ROTATION_COMPONENTS, world_values, selected, poses.status)
        local_values = np.full_like(rotations, np.nan)
        local_values[local_present] = canonical_quaternion_array(local[local_present])
        retain(ChannelKind.ROTATIONS_LOCAL, self.names, ROTATION_COMPONENTS, local_values, local_present)
        diagnostics = np.stack((measured, residuals), axis=-1)
        retain(ChannelKind.RIGID_BODY_RESIDUALS, self.names, ("measured_length", "residual"), diagnostics, np.isfinite(diagnostics))
        if self.bundle.skeleton.joints:
            angle_names = tuple(name for joint in self.bundle.skeleton.joints.values() for name in joint.angle_names)
            angle_values = np.full_like(joints.angles, np.nan)
            angle_values[joint_selected] = canonical_joint_angle_array(joints.angles[joint_selected])
            angle_values = angle_values.reshape((frame_count, len(angle_names), 1))
            angle_presence = np.broadcast_to(joint_selected[..., None], joints.angles.shape).reshape(angle_values.shape)
            retain(ChannelKind.JOINT_ANGLES, angle_names, ("radians",), angle_values, angle_presence)
        if self.compute_center_of_mass:
            center_values = np.full((frame_count, 1, len(POSITION_COMPONENTS)), np.nan)
            center_presence = np.zeros((frame_count, 1), dtype=bool)
            if center is not None:
                center_values[:, 0] = np.where(center.body_present[:, None], center.body_positions, np.nan)
                center_presence[:, 0] = center.body_present
            retain(ChannelKind.DERIVED_POINTS, ("center_of_mass",), POSITION_COMPONENTS, center_values, center_presence)
        return tuple(tensors)
