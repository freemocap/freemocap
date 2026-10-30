"""Calibration initialization uses camera order to resolve equally supported edges."""

from itertools import permutations

import pytest

from freemocap.core.tasks.calibration.shared.transform_math import (
    build_maximum_spanning_tree, find_spanning_tree_pairs,
)


@pytest.mark.parametrize('edge_order', list(permutations((('z', 'a'), ('z', 'm'), ('a', 'm')))))
def test_equal_support_uses_declared_camera_order(edge_order):
    counts = {edge: 10 for edge in edge_order}
    counts.update({(second, first): weight for (first, second), weight in tuple(counts.items())})
    graph = build_maximum_spanning_tree(connection_counts=counts, n_nodes=3, node_ids=['z', 'a', 'm'])
    assert graph == {'z': ['a', 'm'], 'a': ['z'], 'm': ['z']}
    assert find_spanning_tree_pairs(graph=graph) == [('z', 'a'), ('z', 'm')]


def test_stronger_observation_support_precedes_camera_order():
    graph = build_maximum_spanning_tree(connection_counts={('a', 'm'): 10, ('z', 'm'): 5, ('z', 'a'): 4},
                                       n_nodes=3, node_ids=['z', 'a', 'm'])
    assert find_spanning_tree_pairs(graph=graph) == [('a', 'm'), ('m', 'z')]


def test_disconnected_graph_reports_string_camera_identities():
    with pytest.raises(ValueError, match="Component map:.*'missing camera'"):
        build_maximum_spanning_tree(connection_counts={('camera a', 'camera b'): 10},
                                   n_nodes=3, node_ids=['camera a', 'camera b', 'missing camera'])
