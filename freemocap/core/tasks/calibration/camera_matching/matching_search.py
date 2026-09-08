"""Bounded exact search over cached pairwise camera assignment costs."""

import numpy as np

from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    AssignmentSearchResult,
    PairAssignmentCosts,
    ScoredAssignment,
)


def search_camera_assignments(*, evidence: PairAssignmentCosts, maximum_nodes: int) -> AssignmentSearchResult:
    """Return the best two injective assignments; incomplete results are provisional."""
    if maximum_nodes < 1:
        raise ValueError("Search node budget must be positive")
    order = sorted(
        range(evidence.source_count),
        key=lambda source: -sum(source in edge for edge in evidence.edges),
    )
    leaders: list[ScoredAssignment] = []
    assigned: dict[int, int] = {}
    expanded_nodes = 0
    complete = True

    def lower_bound() -> float:
        available = [camera for camera in range(evidence.camera_count) if camera not in assigned.values()]
        total = 0.0
        for edge_index, (left, right) in enumerate(evidence.edges):
            left_options = [assigned[left]] if left in assigned else available
            right_options = [assigned[right]] if right in assigned else available
            total += min(
                (float(evidence.costs[edge_index, a, b])
                 for a in left_options for b in right_options if a != b),
                default=float("inf"),
            )
        return total / len(evidence.edges)

    def visit(depth: int) -> None:
        nonlocal expanded_nodes, complete
        if expanded_nodes >= maximum_nodes:
            complete = False
            return
        expanded_nodes += 1
        bound = lower_bound()
        if not np.isfinite(bound) or (len(leaders) == 2 and bound > leaders[1].mean_cost):
            return
        if depth == len(order):
            leaders.append(ScoredAssignment(
                camera_indices=tuple(assigned[source] for source in range(evidence.source_count)),
                mean_cost=bound,
            ))
            leaders.sort(key=lambda candidate: (candidate.mean_cost, candidate.camera_indices))
            del leaders[2:]
            return
        source = order[depth]
        for camera in range(evidence.camera_count):
            if camera in assigned.values():
                continue
            assigned[source] = camera
            visit(depth + 1)
            del assigned[source]
            if not complete:
                return

    visit(0)
    return AssignmentSearchResult(
        best=leaders[0] if leaders else None,
        runner_up=leaders[1] if len(leaders) > 1 else None,
        complete=complete,
        expanded_nodes=expanded_nodes,
    )
