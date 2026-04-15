"""
Rigid body segment estimation from skeleton keypoint positions.

Computes a 6-DOF pose (position + orientation) and length for each bone
segment, treating each bone as a cylinder with:
    - Origin at the parent joint
    - Local +Z axis pointing from parent toward child
    - Roll pinned to zero via a world-up vector constraint
    - Length from the current bone length estimate

The zero-roll constraint uses a look-at construction:
    1. Z = normalize(child - parent)                # bone direction
    2. X = normalize(cross(world_up, Z))             # sideways
    3. Y = cross(Z, X)                               # completes right-handed frame
    4. Rotation matrix [X | Y | Z] → quaternion

When the bone is nearly parallel to world_up, a fallback up vector is
used to prevent degeneracy.

Usage:
    from rigid_body_estimator import estimate_rigid_bodies, RigidBodyPose

    poses: dict[str, RigidBodyPose] = estimate_rigid_bodies(
        positions=filtered_keypoint_positions,
        skeleton=skeleton_definition,
        bone_lengths=current_bone_lengths,
    )
    # poses["left_shoulder->left_elbow"].position  → (x, y, z) at shoulder
    # poses["left_shoulder->left_elbow"].orientation  → (w, x, y, z) quaternion
    # poses["left_shoulder->left_elbow"].length  → float meters
"""

import numpy as np
import msgspec

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import \
    SkeletonDefinition

# World-up vector for zero-roll constraint (Y-up, matching freemocap convention).
_WORLD_UP: np.ndarray = np.array([0.0, 1.0, 0.0])

# Fallback up vector when bone direction is nearly parallel to world-up.
_FALLBACK_UP: np.ndarray = np.array([0.0, 0.0, 1.0])

# Dot product threshold: if abs(dot(bone_dir, world_up)) exceeds this,
# the bone is nearly vertical and we switch to the fallback up vector.
_PARALLEL_THRESHOLD: float = 0.999


class RigidBodyPose(msgspec.Struct, frozen=True):
    """Pose of a single rigid body segment (bone).

    All fields use plain Python types for clean JSON serialization.
    """
    bone_key: str
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]  # [w, x, y, z] quaternion
    length: float


def _rotation_matrix_to_quaternion(r: np.ndarray) -> tuple[float, float, float, float]:
    """Convert a 3x3 rotation matrix to a unit quaternion (w, x, y, z).

    Uses Shepperd's method for numerical stability across all rotations.
    """
    trace = r[0, 0] + r[1, 1] + r[2, 2]

    if trace > 0.0:
        s = 2.0 * np.sqrt(trace + 1.0)
        w = 0.25 * s
        x = (r[2, 1] - r[1, 2]) / s
        y = (r[0, 2] - r[2, 0]) / s
        z = (r[1, 0] - r[0, 1]) / s
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = 2.0 * np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2])
        w = (r[2, 1] - r[1, 2]) / s
        x = 0.25 * s
        y = (r[0, 1] + r[1, 0]) / s
        z = (r[0, 2] + r[2, 0]) / s
    elif r[1, 1] > r[2, 2]:
        s = 2.0 * np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2])
        w = (r[0, 2] - r[2, 0]) / s
        x = (r[0, 1] + r[1, 0]) / s
        y = 0.25 * s
        z = (r[1, 2] + r[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1])
        w = (r[1, 0] - r[0, 1]) / s
        x = (r[0, 2] + r[2, 0]) / s
        y = (r[1, 2] + r[2, 1]) / s
        z = 0.25 * s

    q = np.array([w, x, y, z])
    q = q / np.linalg.norm(q)
    if q[0] < 0.0:
        q = -q
    return (float(q[0]), float(q[1]), float(q[2]), float(q[3]))


def _look_at_rotation(direction: np.ndarray) -> np.ndarray:
    """Build a rotation matrix with +Z along ``direction`` and roll pinned to zero.

    Args:
        direction: (3,) unit vector pointing from parent to child.

    Returns:
        (3, 3) rotation matrix whose columns are [X, Y, Z] of the local frame.
    """
    z_axis = direction

    # Choose up vector, falling back if bone is nearly vertical
    if abs(float(np.dot(z_axis, _WORLD_UP))) > _PARALLEL_THRESHOLD:
        up = _FALLBACK_UP.copy()
    else:
        up = _WORLD_UP.copy()

    x_axis = np.cross(up, z_axis)
    x_norm = float(np.linalg.norm(x_axis))
    if x_norm < 1e-12:
        x_axis = np.array([1.0, 0.0, 0.0])
        y_axis = np.cross(z_axis, x_axis)
        y_norm = float(np.linalg.norm(y_axis))
        if y_norm < 1e-12:
            return np.eye(3)
        y_axis = y_axis / y_norm
        x_axis = np.cross(y_axis, z_axis)
    else:
        x_axis = x_axis / x_norm

    y_axis = np.cross(z_axis, x_axis)

    rotation = np.column_stack([x_axis, y_axis, z_axis])
    return rotation


def estimate_rigid_bodies(
    *,
    positions: dict[str, np.ndarray],
    skeleton: SkeletonDefinition,
    bone_lengths: dict[str, float],
) -> dict[str, RigidBodyPose]:
    """Compute rigid body poses for all bone segments with both endpoints present.

    Bones whose parent or child keypoint is missing from ``positions`` are
    silently skipped — only bones with both joints present get a pose.

    Args:
        positions: keypoint positions, mapping name → (3,) array.
        skeleton: skeleton topology defining bone parent→child pairs.
        bone_lengths: mapping "parent->child" → length in meters.

    Returns:
        Dict mapping bone key ("parent->child") → RigidBodyPose.
    """
    poses: dict[str, RigidBodyPose] = {}

    for bone in skeleton.bones:
        parent_pos = positions.get(bone.parent)
        child_pos = positions.get(bone.child)

        if parent_pos is None or child_pos is None:
            continue

        parent_f64 = np.asarray(parent_pos, dtype=np.float64)
        child_f64 = np.asarray(child_pos, dtype=np.float64)

        direction = child_f64 - parent_f64
        dist = float(np.linalg.norm(direction))

        if dist < 1e-12:
            continue

        direction_unit = direction / dist

        rotation = _look_at_rotation(direction=direction_unit)
        quaternion = _rotation_matrix_to_quaternion(rotation)

        length = bone_lengths.get(bone.key, dist)

        poses[bone.key] = RigidBodyPose(
            bone_key=bone.key,
            position=(float(parent_f64[0]), float(parent_f64[1]), float(parent_f64[2])),
            orientation=quaternion,
            length=length,
        )

    return poses
