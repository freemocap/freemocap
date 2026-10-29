"""Explicit scalar materialization only for comparison with the live solver oracle."""
import numpy as np
from skellyforge.core.skeleton.pose.rigid_body_diagnostics import RigidBodyResidual
from freemocap.core.skeletons.skeleton_reconstruction import SkeletonReconstruction


def reconstruction_frame(result, index, bundle):
    def named(kind):
        tensor = result.channel_tensor(kind)
        available = tensor.companion_values("entry_presence")[index].all(axis=-1)
        names = tensor.tensor_layout.axes[1].identifiers
        return {names[column]: tensor.data_values[index, column] for column in np.flatnonzero(available)}
    mapped = named("MAPPED_KEYPOINTS_3D")
    if not mapped:
        return None
    status = result.channel_tensor("SEGMENT_ORIGINS").companion_values("solver_status")[index]
    if not np.any(status == 1):
        return SkeletonReconstruction(model_id=result.model_id, mapped_keypoints=mapped)
    diagnostics = result.channel_tensor("RIGID_BODY_RESIDUALS")
    def optional(value):
        return float(value) if np.isfinite(value) else None
    fit = result.scale_fit
    residuals = {name: RigidBodyResidual(measured_length=optional(diagnostics.data_values[index, column, 0]),
        residual=optional(diagnostics.data_values[index, column, 1]),
        reference_length=fit.segment_lengths[name] if fit else None, reference_kind=result.residual_reference)
        for column, name in enumerate(diagnostics.tensor_layout.axes[1].identifiers)}
    angles = None
    if bundle.skeleton.joints:
        flattened = named("JOINT_ANGLES")
        angles = {name: tuple(float(flattened[angle][0]) for angle in joint.angle_names)
                  for name, joint in bundle.skeleton.joints.items() if all(angle in flattened for angle in joint.angle_names)}
    center = named("DERIVED_POINTS").get("center_of_mass") if result.compute_center_of_mass else None
    return SkeletonReconstruction(model_id=result.model_id, mapped_keypoints=mapped,
        landmarks=named("LANDMARKS_3D"), segment_origins=named("SEGMENT_ORIGINS"),
        segment_rotations_world=named("ROTATIONS_WORLD"), segment_rotations_local=named("ROTATIONS_LOCAL"),
        segment_lengths=dict(fit.segment_lengths) if fit else {}, fitted_scale_mm=fit.fitted_scale if fit else None,
        rigid_body_residuals=residuals, joint_angles=angles, center_of_mass=center)


def _finite_frame_points(
    *, frame: np.ndarray, point_names: tuple[str, ...],
) -> dict[str, np.ndarray]:
    """Adapt finite XYZ values to the scalar test oracle; never used by production."""
    valid_indices = np.flatnonzero(np.isfinite(frame).all(axis=1))
    return {point_names[index]: frame[index] for index in valid_indices}
