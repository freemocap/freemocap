"""
FABRIK (Forward And Backward Reaching Inverse Kinematics) solver
with full tree support including Y-splits.

Handles:
    - Linear chains (arm: shoulder → elbow → wrist)
    - Y-splits (ankle → heel + foot_index)
    - Multi-branch trees (wrist → 5 fingers)
    - Multiple disjoint trees (separate arm/leg trees)

Tree topology is decoupled from bone lengths: the FabrikTree stores
parent/child relationships and traversal order, while bone lengths
are passed to solve_tree() as a separate dict. This allows bone
lengths to be updated per-frame (e.g. from a running estimator)
without rebuilding the tree.

Algorithm (tree extension of Aristidou & Lasenby 2011):
    Forward pass (leaves → roots):
        1. Snap each leaf to its target position
        2. Walk inward in reverse topological order
        3. At each node, enforce bone length toward parent
        4. At branch points, average positions from all children
    Backward pass (roots → leaves):
        1. Fix each root at its target position
        2. Walk outward in topological order
        3. At each node, enforce bone length from parent

Usage:
    tree = FabrikTree.from_skeleton(skeleton=skel)
    solved = solve_tree(targets=positions, tree=tree, bone_lengths=lengths)
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from freemocap.core.tasks.mocap.skeleton_dewiggler.dewiggling_methods.mediapipe_skeleton_config import \
    SkeletonDefinition


# ============================================================
# Tree Data Structure
# ============================================================


@dataclass(frozen=True)
class FabrikNode:
    """Single node in a FABRIK tree."""

    name: str
    parent_name: str | None
    children_names: tuple[str, ...]
    bone_key: str | None  # "parent->child" key for bone_lengths lookup, None for roots

    @property
    def is_root(self) -> bool:
        return self.parent_name is None

    @property
    def is_leaf(self) -> bool:
        return len(self.children_names) == 0

    @property
    def is_branch(self) -> bool:
        return len(self.children_names) > 1


@dataclass(frozen=True)
class FabrikTree:
    """
    Forest of FABRIK trees built from a SkeletonDefinition.

    Stores topology only — bone lengths are passed separately to solve_tree().
    Nodes are stored in topological order (roots first, leaves last).
    """

    nodes: dict[str, FabrikNode]
    topo_order: tuple[str, ...]  # roots first → leaves last
    root_names: frozenset[str]
    leaf_names: frozenset[str]
    bone_keys: frozenset[str]  # all "parent->child" keys in this tree

    @classmethod
    def from_skeleton(
        cls,
        *,
        skeleton: SkeletonDefinition,
    ) -> "FabrikTree":
        """
        Build FABRIK tree topology from skeleton bones.

        Args:
            skeleton: skeleton topology (bones define tree edges).
        """
        if not skeleton.bones:
            return cls(
                nodes={},
                topo_order=(),
                root_names=frozenset(),
                leaf_names=frozenset(),
                bone_keys=frozenset(),
            )

        # Build adjacency: parent → [children]
        children_of: dict[str, list[str]] = {}
        parent_of: dict[str, str] = {}
        bone_joints: set[str] = set()

        for bone in skeleton.bones:
            children_of.setdefault(bone.parent, []).append(bone.child)
            parent_of[bone.child] = bone.parent
            bone_joints.add(bone.parent)
            bone_joints.add(bone.child)

        # Find roots: joints in bones that have no parent in bone graph
        root_names: set[str] = set()
        for joint in bone_joints:
            if joint not in parent_of:
                root_names.add(joint)

        if not root_names:
            raise ValueError("No root joints found — bone graph may contain cycles")

        # BFS topological order from roots
        topo_order: list[str] = []
        visited: set[str] = set()
        queue: deque[str] = deque()

        for root in sorted(root_names):  # sorted for determinism
            queue.append(root)
            visited.add(root)

        while queue:
            name = queue.popleft()
            topo_order.append(name)
            for child in children_of.get(name, []):
                if child in visited:
                    raise ValueError(f"Cycle detected at joint '{child}'")
                visited.add(child)
                queue.append(child)

        # Build nodes
        nodes: dict[str, FabrikNode] = {}
        leaf_names: set[str] = set()
        bone_keys: set[str] = set()

        for name in topo_order:
            children = tuple(children_of.get(name, []))
            parent = parent_of.get(name)

            bone_key: str | None = None
            if parent is not None:
                bone_key = f"{parent}->{name}"
                bone_keys.add(bone_key)

            nodes[name] = FabrikNode(
                name=name,
                parent_name=parent,
                children_names=children,
                bone_key=bone_key,
            )

            if not children:
                leaf_names.add(name)

        return cls(
            nodes=nodes,
            topo_order=tuple(topo_order),
            root_names=frozenset(root_names),
            leaf_names=frozenset(leaf_names),
            bone_keys=frozenset(bone_keys),
        )

    def validate_bone_lengths(self, bone_lengths: dict[str, float]) -> None:
        """Validate that bone_lengths covers all bones in this tree with positive values."""
        for bone_key in self.bone_keys:
            if bone_key not in bone_lengths:
                raise ValueError(f"Missing bone length for '{bone_key}'")
            if bone_lengths[bone_key] <= 0.0:
                raise ValueError(
                    f"Bone length must be positive for '{bone_key}', "
                    f"got {bone_lengths[bone_key]}"
                )


# ============================================================
# Tree FABRIK Solver
# ============================================================


_FALLBACK_DIRECTION: np.ndarray = np.array([0.0, 1.0, 0.0])


def _enforce_bone_length(
    from_pos: np.ndarray,
    to_pos: np.ndarray,
    length: float,
) -> np.ndarray:
    """Move ``to_pos`` to be exactly ``length`` away from ``from_pos``."""
    direction = to_pos - from_pos
    dist = float(np.linalg.norm(direction))
    if dist < 1e-12:
        direction = _FALLBACK_DIRECTION.copy()
        dist = 1.0
    return from_pos + (direction / dist) * length


def solve_fabrik_tree(
    *,
    targets: dict[str, np.ndarray],
    tree: FabrikTree,
    bone_lengths: dict[str, float],
    tolerance: float = 1e-4,
    max_iterations: int = 20,
) -> dict[str, np.ndarray]:
    """
    Solve FABRIK for a tree structure with Y-splits.

    Root joints are held fixed at their target positions.
    Leaf joints are pulled toward their target positions.
    Branch points average the constraints from all children.

    Args:
        targets: target positions for all joints in the tree,
                 mapping name → (3,) array.
        tree: FABRIK tree topology.
        bone_lengths: mapping "parent->child" → length in meters.
                      Must cover all bones in the tree.
        tolerance: convergence threshold on leaf end-effector error.
        max_iterations: max forward/backward iterations.

    Returns:
        Solved joint positions mapping name → (3,) array.
    """
    if not tree.nodes:
        return {}

    # Validate inputs
    for name in tree.topo_order:
        if name not in targets:
            raise ValueError(f"Missing target position for joint '{name}'")

    for bone_key in tree.bone_keys:
        if bone_key not in bone_lengths:
            raise ValueError(f"Missing bone length for '{bone_key}'")

    positions: dict[str, np.ndarray] = {
        name: np.array(targets[name], dtype=np.float64)
        for name in tree.topo_order
    }

    for _ in range(max_iterations):
        # === FORWARD PASS: leaves → roots ===
        suggested: dict[str, list[np.ndarray]] = {}

        for name in reversed(tree.topo_order):
            node = tree.nodes[name]

            if node.is_leaf:
                positions[name] = np.array(targets[name], dtype=np.float64)
            elif name in suggested:
                positions[name] = np.mean(suggested[name], axis=0)

            if node.parent_name is not None:
                assert node.bone_key is not None
                length = bone_lengths[node.bone_key]
                suggested_parent = _enforce_bone_length(
                    from_pos=positions[name],
                    to_pos=positions[node.parent_name],
                    length=length,
                )
                suggested.setdefault(node.parent_name, []).append(suggested_parent)

        # === BACKWARD PASS: roots → leaves ===
        for name in tree.topo_order:
            node = tree.nodes[name]

            if node.is_root:
                positions[name] = np.array(targets[name], dtype=np.float64)
            else:
                assert node.parent_name is not None
                assert node.bone_key is not None
                length = bone_lengths[node.bone_key]
                positions[name] = _enforce_bone_length(
                    from_pos=positions[node.parent_name],
                    to_pos=positions[name],
                    length=length,
                )

        # === CONVERGENCE CHECK ===
        converged = True
        for leaf_name in tree.leaf_names:
            error = float(np.linalg.norm(positions[leaf_name] - targets[leaf_name]))
            if error > tolerance:
                converged = False
                break
        if converged:
            break

    return positions


# ============================================================
# Bone Length Estimation (simple median, for offline/batch use)
# ============================================================


def estimate_bone_lengths(
    *,
    frames: list[dict[str, np.ndarray]],
    skeleton: SkeletonDefinition,
) -> dict[str, float]:
    """
    Estimate bone lengths as median distance across calibration frames.

    For online estimation with priors, use BoneLengthEstimator instead.

    Args:
        frames: list of position dicts (one per frame),
                each mapping keypoint name → (3,) array.
        skeleton: skeleton whose bones to measure.

    Returns:
        Dict mapping "parent->child" → median bone length.
    """
    if not frames:
        raise ValueError("Need at least one frame to estimate bone lengths")

    if not skeleton.bones:
        return {}

    bone_samples: dict[str, list[float]] = {
        bone.key: [] for bone in skeleton.bones
    }

    for positions in frames:
        for bone in skeleton.bones:
            parent_pos = positions.get(bone.parent)
            child_pos = positions.get(bone.child)
            if parent_pos is None or child_pos is None:
                continue
            dist = float(np.linalg.norm(
                np.asarray(parent_pos) - np.asarray(child_pos)
            ))
            bone_samples[bone.key].append(dist)

    bone_lengths: dict[str, float] = {}
    for bone_key, samples in bone_samples.items():
        if not samples:
            raise ValueError(f"No samples found for bone '{bone_key}'")
        bone_lengths[bone_key] = float(np.median(samples))

    return bone_lengths
