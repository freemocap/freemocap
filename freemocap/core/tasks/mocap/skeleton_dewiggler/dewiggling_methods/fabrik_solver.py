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

Algorithm (tree FABRIK for a fully-observed skeleton):
    Forward pass (leaves → roots):
        1. Snap each tracked joint (leaf or linear-chain node) to its target
        2. Walk inward in reverse topological order, enforcing bone length
           toward the parent
        3. At branch points, position as the mean of all children's suggestions
    Backward pass (roots → leaves):
        1. Fix each root at its target position
        2. Walk outward in topological order, enforcing bone length from parent
    Iterate until joints settle (max inter-iteration movement < tolerance).

Usage:
    tree = FabrikTree.from_joint_hierarchy(joint_hierarchy=hierarchy)
    solved = solve_fabrik_tree(targets=positions, tree=tree, bone_lengths=lengths)
"""

from collections import deque
from dataclasses import dataclass

import numpy as np


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
    Forest of FABRIK trees built from a canonical joint hierarchy.

    Stores topology only — bone lengths are passed separately to
    solve_fabrik_tree(). Nodes are stored in topological order
    (roots first, leaves last).
    """

    nodes: dict[str, FabrikNode]
    topo_order: tuple[str, ...]  # roots first → leaves last
    root_names: frozenset[str]
    leaf_names: frozenset[str]
    bone_keys: frozenset[str]  # all "parent->child" keys in this tree

    @classmethod
    def from_joint_hierarchy(
        cls,
        *,
        joint_hierarchy: dict[str, list[str]],
    ) -> "FabrikTree":
        """
        Build FABRIK tree topology directly from a joint hierarchy dict.

        Trees are built from canonical anatomical models without
        tracker-specific naming.

        Args:
            joint_hierarchy: mapping parent → [children]. The roots are
                             keys that never appear as children.
        """
        if not joint_hierarchy:
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

        for parent, children in joint_hierarchy.items():
            bone_joints.add(parent)
            for child in children:
                if child in parent_of:
                    raise ValueError(
                        f"Joint '{child}' has two parents: "
                        f"'{parent_of[child]}' and '{parent}'"
                    )
                parent_of[child] = parent
                bone_joints.add(child)
            children_of[parent] = list(children)

        # Find roots: joints that have no parent
        root_names: set[str] = set()
        for joint in bone_joints:
            if joint not in parent_of:
                root_names.add(joint)

        if not root_names:
            raise ValueError("No root joints found — hierarchy may contain cycles")

        # BFS topological order from roots
        topo_order: list[str] = []
        visited: set[str] = set()
        queue: deque[str] = deque()

        for root in sorted(root_names):
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
    tolerance: float = 0.1,   # mm — convergence threshold (was 1e-4 meters)
    max_iterations: int = 20,
    initial_positions: dict[str, np.ndarray] | None = None,
) -> dict[str, np.ndarray]:
    """
    Solve FABRIK for a tree structure with Y-splits.

    Every directly-tracked joint (root, leaf, or linear-chain intermediate) is
    snapped to its target each forward pass; branch points (one parent, many
    children) are positioned as the mean of their children's suggestions. Bone
    lengths are then enforced from the roots outward, so the result keeps each
    joint's observed direction while holding the (adaptive) bone lengths.

    Args:
        targets: target positions for all joints in the tree,
                 mapping name → (3,) array (mm).
        tree: FABRIK tree topology.
        bone_lengths: mapping "parent->child" → length in mm.
                      Must cover all bones in the tree.
        tolerance: settling threshold (mm) — stop once no joint moves more
                   than this between successive iterations.
        max_iterations: max forward/backward iterations.
        initial_positions: optional starting positions for each joint.
                           If provided, used instead of ``targets`` as the
                           initial guess.  Warm-starting from the previous
                           frame's solution dramatically reduces iterations
                           needed for convergence.

    Returns:
        Solved joint positions mapping name → (3,) array (mm).
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

    if initial_positions is not None:
        # Warm-start: use previous solution translated to current root.
        # Global translation is removed so FABRIK only needs to resolve
        # the differential pose change, which is small frame-to-frame.
        positions: dict[str, np.ndarray] = {}
        for name in tree.topo_order:
            if name in initial_positions:
                positions[name] = np.array(initial_positions[name], dtype=np.float64)
            else:
                positions[name] = np.array(targets[name], dtype=np.float64)
    else:
        positions: dict[str, np.ndarray] = {
            name: np.array(targets[name], dtype=np.float64)
            for name in tree.topo_order
        }

    for _ in range(max_iterations):
        prev_positions = {name: positions[name].copy() for name in tree.topo_order}

        # === FORWARD PASS: leaves → roots ===
        suggested: dict[str, list[np.ndarray]] = {}

        for name in reversed(tree.topo_order):
            node = tree.nodes[name]

            if node.is_branch:
                # Branch point (multiple children): position is the average
                # of child suggestions. These are computed landmarks whose
                # tracker "target" is derived from other points.
                if name in suggested:
                    positions[name] = np.mean(suggested[name], axis=0)
            else:
                # Leaf or linear-chain intermediate node: snap to tracker
                # target.  Every directly-tracked joint constrains the
                # skeleton, not just the endpoints of each chain.
                positions[name] = np.array(targets[name], dtype=np.float64)

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
        # FABRIK has settled once joints stop moving between iterations.
        # (Comparing against the raw targets never converges here: enforcing
        # bone lengths deliberately pulls joints off their mutually
        # inconsistent observed targets, so that error stays nonzero.)
        max_shift = 0.0
        for name in tree.topo_order:
            shift = float(np.linalg.norm(positions[name] - prev_positions[name]))
            if shift > max_shift:
                max_shift = shift
        if max_shift < tolerance:
            break

    return positions
