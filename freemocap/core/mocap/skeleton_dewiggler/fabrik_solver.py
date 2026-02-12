"""
FABRIK (Forward And Backward Reaching Inverse Kinematics) solver
with full tree support including Y-splits.

Handles:
    - Linear chains (arm: shoulder → elbow → wrist)
    - Y-splits (ankle → heel + foot_index)
    - Multi-branch trees (wrist → 5 fingers)
    - Multiple disjoint trees (separate arm/leg trees)

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
    tree = FabrikTree.from_skeleton(skeleton=skel, bone_lengths=lengths)
    solved = solve_tree(targets=filtered_positions, tree=tree)
"""

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from mediapipe_skeleton_config import Bone, SkeletonDefinition


# ============================================================
# Tree Data Structure
# ============================================================


@dataclass(frozen=True)
class FabrikNode:
    """Single node in a FABRIK tree."""

    name: str
    parent_name: str | None
    children_names: tuple[str, ...]
    bone_length_to_parent: float | None  # None for root nodes

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

    Nodes are stored in topological order (roots first, leaves last).
    """

    nodes: dict[str, FabrikNode]
    topo_order: tuple[str, ...]  # roots first → leaves last
    root_names: frozenset[str]
    leaf_names: frozenset[str]

    @classmethod
    def from_skeleton(
        cls,
        *,
        skeleton: SkeletonDefinition,
        bone_lengths: dict[str, float],
    ) -> "FabrikTree":
        """
        Build FABRIK tree(s) from skeleton bones and measured bone lengths.

        Args:
            skeleton: skeleton topology (bones define tree edges).
            bone_lengths: mapping of "parent->child" → length (meters).
                          Must contain an entry for every bone.
        """
        if not skeleton.bones:
            return cls(
                nodes={},
                topo_order=(),
                root_names=frozenset(),
                leaf_names=frozenset(),
            )

        # Validate bone lengths
        for bone in skeleton.bones:
            if bone.key not in bone_lengths:
                raise ValueError(f"Missing bone length for '{bone.key}'")
            if bone_lengths[bone.key] <= 0.0:
                raise ValueError(f"Bone length must be positive for '{bone.key}', got {bone_lengths[bone.key]}")

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

        for name in topo_order:
            children = tuple(children_of.get(name, []))
            parent = parent_of.get(name)

            bl: float | None = None
            if parent is not None:
                bl = bone_lengths[f"{parent}->{name}"]

            nodes[name] = FabrikNode(
                name=name,
                parent_name=parent,
                children_names=children,
                bone_length_to_parent=bl,
            )

            if not children:
                leaf_names.add(name)

        return cls(
            nodes=nodes,
            topo_order=tuple(topo_order),
            root_names=frozenset(root_names),
            leaf_names=frozenset(leaf_names),
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


def solve_tree(
    *,
    targets: dict[str, np.ndarray],
    tree: FabrikTree,
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
        tree: FABRIK tree structure with bone lengths.
        tolerance: convergence threshold on leaf end-effector error.
        max_iterations: max forward/backward iterations.

    Returns:
        Solved joint positions mapping name → (3,) array.
    """
    if not tree.nodes:
        return {}

    # Validate targets
    for name in tree.topo_order:
        if name not in targets:
            raise ValueError(f"Missing target position for joint '{name}'")

    positions: dict[str, np.ndarray] = {
        name: np.array(targets[name], dtype=np.float64)
        for name in tree.topo_order
    }

    for _ in range(max_iterations):
        # === FORWARD PASS: leaves → roots ===
        # Process in reverse topological order (leaves first)
        # At each node: enforce bone length toward parent.
        # At branch points: average positions from children first.
        suggested: dict[str, list[np.ndarray]] = {}

        for name in reversed(tree.topo_order):
            node = tree.nodes[name]

            if node.is_leaf:
                # Snap leaf to target
                positions[name] = np.array(targets[name], dtype=np.float64)
            elif name in suggested:
                # Branch or internal node: average child-suggested positions
                positions[name] = np.mean(suggested[name], axis=0)

            # Suggest a position for parent based on bone constraint
            if node.parent_name is not None:
                assert node.bone_length_to_parent is not None
                suggested_parent = _enforce_bone_length(
                    from_pos=positions[name],
                    to_pos=positions[node.parent_name],
                    length=node.bone_length_to_parent,
                )
                suggested.setdefault(node.parent_name, []).append(suggested_parent)

        # === BACKWARD PASS: roots → leaves ===
        # Fix roots, push outward enforcing bone lengths
        for name in tree.topo_order:
            node = tree.nodes[name]

            if node.is_root:
                # Root stays fixed at target
                positions[name] = np.array(targets[name], dtype=np.float64)
            else:
                assert node.parent_name is not None
                assert node.bone_length_to_parent is not None
                positions[name] = _enforce_bone_length(
                    from_pos=positions[node.parent_name],
                    to_pos=positions[name],
                    length=node.bone_length_to_parent,
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
# Bone Length Estimation
# ============================================================


def estimate_bone_lengths(
    *,
    frames: list[dict[str, np.ndarray]],
    skeleton: SkeletonDefinition,
) -> dict[str, float]:
    """
    Estimate bone lengths as median distance across calibration frames.

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
