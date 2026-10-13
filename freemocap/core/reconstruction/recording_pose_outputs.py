"""Compose Forge's prepared array calculations after sequential roll resolution.

Only object packing loops over frames/segments. Geometry runs on chunk arrays.
"""
import numpy as np
from skellyforge.core.biomechanics.center_of_mass_batch import CenterOfMassGeometry
from skellyforge.core.math.geometry.rotation_quaternion import (
    conjugate_quaternion_array, hamilton_product, normalize_quaternion_array,
)
from skellyforge.core.skeleton.chain.anchored_batch import AnchoredSkeletonGeometry
from skellyforge.core.skeleton.linkage.joint_batch import JointBatchGeometry
from skellyforge.core.skeleton.pose.model_scale_fitting import ModelScaleFit, scale_voting_segment_names
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import ResidualBatchGeometry, RigidBodyResidual
from skellyforge.core.skeleton.skeleton_pose import SkeletonPose

from freemocap.core.skeletons.rotation_output import canonical_joint_angles, canonical_quaternion_outputs
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction
from freemocap.core.skeletons.tracked_skeleton_bundle import TrackedSkeletonBundle


class RecordingPoseOutputs:
    """Fixed fit/model plans reused for every chunk in one recording."""

    def __init__(self, *, bundle: TrackedSkeletonBundle, fit: ModelScaleFit | None,
                 compute_center_of_mass: bool):
        self.bundle = bundle
        self.fit = fit
        self.names = tuple(bundle.skeleton.segments)
        self.indices = {name: i for i, name in enumerate(self.names)}
        self.parents = np.array([self.indices.get(bundle.rest_pose.parents[n], self.indices[n]) for n in self.names])
        self.roots = np.array([bundle.rest_pose.parents[n] is None for n in self.names])
        self.positions = AnchoredSkeletonGeometry.from_skeleton(skeleton=bundle.skeleton,
            fit=fit, anchor_segment_name=bundle.anchor_segment_name or bundle.rest_pose.root_segment_name) if fit else None
        self.joints = JointBatchGeometry.from_skeleton(skeleton=bundle.skeleton)
        self.residuals = ResidualBatchGeometry.from_skeleton(skeleton=bundle.skeleton,
            measured_segment_names=frozenset(scale_voting_segment_names(skeleton=bundle.skeleton,
                measured_landmark_names=bundle.landmark_mapping.directly_measured_landmark_names)),
            reference_lengths=fit.segment_lengths if fit else {}, reference_kind='recording_fit')
        self.center = CenterOfMassGeometry.from_definitions(definitions=bundle.center_of_mass_definitions,
            landmark_names=self.positions.landmark_names, segment_masses=bundle.segment_masses
        ) if compute_center_of_mass and self.positions and bundle.center_of_mass_definitions.definitions else None

    def calculate(self, *, poses: list[SkeletonPose], landmarks: list[dict[str, np.ndarray]]) -> list[SkeletonReconstruction | None]:
        shape = (len(poses), len(self.names))
        rotations = np.full((*shape, 4), np.nan)
        origins = np.full((*shape, 3), np.nan)
        scales = np.full(shape, np.nan)
        present = np.zeros(shape, dtype=bool)
        solutions = np.full(shape, None, dtype=object)
        for frame, pose in enumerate(poses):
            for name, segment in pose.segment_poses.items():
                column = self.indices[name]
                rotations[frame, column] = segment.orientation.as_array()
                origins[frame, column] = segment.origin.array
                scales[frame, column] = segment.scale_estimate
                solutions[frame, column] = segment.solved_by
                present[frame, column] = True

        measured, residuals = self.residuals.calculate(scales=scales, segment_present=present)
        joints = self.joints.calculate(world_orientations=rotations, segment_present=present, segment_solutions=solutions)
        selected = np.zeros_like(present)
        connected = None
        if self.positions:
            selected[:, self.positions.anchor_index] = present[:, self.positions.anchor_index]
            # Tree dependencies require depth order; all frames/branches at a depth batch together.
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

        result = []
        for frame, mapped in enumerate(landmarks):
            if not mapped:
                result.append(None)
                continue
            if not present[frame].any():
                result.append(SkeletonReconstruction(model_id=self.bundle.model_id, mapped_keypoints=mapped))
                continue
            def available(value):
                return float(value) if np.isfinite(value) else None
            result.append(SkeletonReconstruction(
                model_id=self.bundle.model_id, mapped_keypoints=mapped,
                rigid_body_residuals={name: RigidBodyResidual(
                    measured_length=available(measured[frame, column]),
                    reference_length=available(self.residuals.reference_lengths[column]),
                    residual=available(residuals[frame, column]), reference_kind='recording_fit')
                    for column, name in enumerate(self.names)},
                segment_origins={self.names[c]: connected.segment_origins[frame, c]
                    for c in np.flatnonzero(selected[frame])},
                landmarks={self.positions.landmark_names[c]: connected.landmark_positions[frame, c]
                    for c in np.flatnonzero(connected.landmark_present[frame])} if connected else {},
                segment_rotations_world=canonical_quaternion_outputs({self.names[c]: rotations[frame, c]
                    for c in np.flatnonzero(selected[frame])}),
                segment_rotations_local=canonical_quaternion_outputs({self.names[c]: local[frame, c]
                    for c in np.flatnonzero(local_present[frame])}),
                segment_lengths=dict(self.fit.segment_lengths) if self.fit else {},
                fitted_scale_mm=self.fit.fitted_scale if self.fit else None,
                joint_angles=canonical_joint_angles({self.joints.joint_names[c]: tuple(joints.angles[frame, c])
                    for c in np.flatnonzero(joint_selected[frame])}) if self.bundle.skeleton.joints else None,
                center_of_mass=center.body_positions[frame] if center is not None and center.body_present[frame] else None,
            ))
        return result
