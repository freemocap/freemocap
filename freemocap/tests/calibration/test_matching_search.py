"""Compare bounded pair-assignment search against exhaustive enumeration."""

import itertools

import numpy as np
import pytest

from freemocap.core.tasks.calibration.camera_matching.matching_models import PairAssignmentCosts
from freemocap.core.tasks.calibration.camera_matching.matching_search import search_camera_assignments


@pytest.mark.parametrize(("sources", "cameras"), [(2, 2), (3, 3), (3, 4), (4, 5)])
def test_search_matches_exhaustive_best_and_runner_up(sources: int, cameras: int) -> None:
    edges = tuple(itertools.combinations(range(sources), 2))
    costs = np.random.default_rng(19).random((len(edges), cameras, cameras))
    evidence = PairAssignmentCosts(source_count=sources, camera_count=cameras, edges=edges, costs=costs)
    expected = sorted(
        (sum(costs[k, p[i], p[j]] for k, (i, j) in enumerate(edges)) / len(edges), p)
        for p in itertools.permutations(range(cameras), sources)
    )
    result = search_camera_assignments(evidence=evidence, maximum_nodes=100_000)
    assert result.complete
    assert result.best is not None and result.runner_up is not None
    assert result.best.camera_indices == expected[0][1]
    assert result.runner_up.camera_indices == expected[1][1]
    assert result.best.mean_cost == pytest.approx(expected[0][0])


def test_equal_costs_retain_competitor_instead_of_claiming_uniqueness() -> None:
    evidence = PairAssignmentCosts(source_count=2, camera_count=2, edges=((0, 1),), costs=np.zeros((1, 2, 2)))
    result = search_camera_assignments(evidence=evidence, maximum_nodes=100)
    assert result.complete and result.best is not None and result.runner_up is not None
    assert result.best.mean_cost == result.runner_up.mean_cost
    assert result.best.camera_indices != result.runner_up.camera_indices


def test_work_limit_is_not_success() -> None:
    evidence = PairAssignmentCosts(source_count=2, camera_count=2, edges=((0, 1),), costs=np.zeros((1, 2, 2)))
    result = search_camera_assignments(evidence=evidence, maximum_nodes=1)
    assert not result.complete
    assert result.expanded_nodes == 1
    assert result.best is None


def test_disconnected_evidence_cannot_hide_sources() -> None:
    with pytest.raises(ValueError, match="Disconnected"):
        PairAssignmentCosts(source_count=3, camera_count=3, edges=((0, 1),), costs=np.zeros((1, 3, 3)))
