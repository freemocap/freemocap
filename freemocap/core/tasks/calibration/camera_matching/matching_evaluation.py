"""Check the supplied binding first, then search and validate fixed geometry."""

import itertools

import numpy as np

from freemocap.core.tasks.calibration.camera_matching.matching_fitness import evaluate_geometry_fitness
from freemocap.core.tasks.calibration.camera_matching.matching_models import (
    CameraMatchingRequest,
    CameraMatchingResult,
    CameraMatchingStatus,
    GeometryFitnessRequest,
    GeometryFitnessStatus,
    PairAssignmentCosts,
)
from freemocap.core.tasks.calibration.camera_matching.matching_search import search_camera_assignments


def _supported_edges(request: CameraMatchingRequest) -> tuple[tuple[int, int], ...]:
    edges: list[tuple[int, int]] = []
    for left, right in itertools.combinations(range(len(request.source_ids)), 2):
        shared = np.isfinite(request.pixels[[left, right]]).all(axis=(0, 3))
        qualifying = shared.sum(axis=-1) >= request.config.minimum_points_per_frame
        if all(int(qualifying[offset::2].sum()) >= request.config.minimum_frames for offset in (0, 1)):
            edges.append((left, right))
    reached = {0}
    while True:
        expanded = reached | {source for edge in edges if reached.intersection(edge) for source in edge}
        if expanded == reached:
            break
        reached = expanded
    return tuple(edges) if len(reached) == len(request.source_ids) else ()


def _pair_cost(*, request: CameraMatchingRequest, edge: tuple[int, int], cameras: tuple[int, int], validation: bool) -> float:
    if any(not request.compatible(source=source, camera=camera) for source, camera in zip(edge, cameras, strict=True)):
        return float("inf")
    fitness = evaluate_geometry_fitness(request=GeometryFitnessRequest(
        cameras=tuple(request.cameras[index] for index in cameras),
        pixels=request.pixels[list(edge), int(validation)::2],
        config=request.config,
    ))
    if fitness.mean_cost is None:
        raise ValueError("Supported matching edge unexpectedly lacks usable observations")
    return fitness.mean_cost


def match_camera_geometry(*, request: CameraMatchingRequest) -> CameraMatchingResult:
    """Return useful provisional assignments without representing them as verified.

    Execution callers own continuation and retry policy. Models and observations are
    never mutated, and the initial binding never triggers a search when it passes.
    """
    initial = request.initial_assignment
    if initial is not None and any(
        not request.compatible(source=source, camera=camera) for source, camera in enumerate(initial)
    ):
        initial = None
    if not request.config.automatically_match:
        return CameraMatchingResult(status=CameraMatchingStatus.DISABLED, assignment=initial, fitness=None, search=None)
    edges = _supported_edges(request)
    if not edges:
        return CameraMatchingResult(status=CameraMatchingStatus.INSUFFICIENT, assignment=initial, fitness=None, search=None)
    if initial is not None:
        search_fitness = evaluate_geometry_fitness(request=request.fitness_request(assignment=initial, validation=False))
        validation_fitness = evaluate_geometry_fitness(request=request.fitness_request(assignment=initial, validation=True))
        if search_fitness.status is GeometryFitnessStatus.ACCEPTABLE and validation_fitness.status is GeometryFitnessStatus.ACCEPTABLE:
            return CameraMatchingResult(
                status=CameraMatchingStatus.INITIAL_ACCEPTED, assignment=initial, fitness=validation_fitness, search=None,
            )

    costs = np.full((len(edges), len(request.cameras), len(request.cameras)), np.inf, dtype=np.float64)
    for left, right in itertools.permutations(range(len(request.cameras)), 2):
        for index, edge in enumerate(edges):
            costs[index, left, right] = _pair_cost(request=request, edge=edge, cameras=(left, right), validation=False)
    search = search_camera_assignments(
        evidence=PairAssignmentCosts(
            source_count=len(request.source_ids), camera_count=len(request.cameras), edges=edges, costs=costs,
        ),
        maximum_nodes=request.config.maximum_search_nodes,
    )
    if not search.complete:
        return CameraMatchingResult(
            status=CameraMatchingStatus.SEARCH_LIMIT,
            assignment=search.best.camera_indices if search.best is not None else initial,
            fitness=None, search=search,
        )
    if search.best is None:
        return CameraMatchingResult(status=CameraMatchingStatus.POOR, assignment=initial, fitness=None, search=search)
    fitness = evaluate_geometry_fitness(request=request.fitness_request(assignment=search.best.camera_indices, validation=True))
    status = CameraMatchingStatus.MATCHED
    if search.runner_up is not None:
        validation_costs = [
            np.mean([
                _pair_cost(request=request, edge=edge, cameras=(candidate.camera_indices[edge[0]], candidate.camera_indices[edge[1]]), validation=True)
                for edge in edges
            ])
            for candidate in (search.best, search.runner_up)
        ]
        if (search.runner_up.mean_cost - search.best.mean_cost < request.config.minimum_score_gap
                or validation_costs[1] - validation_costs[0] < request.config.minimum_score_gap):
            status = CameraMatchingStatus.AMBIGUOUS
    if fitness.status is not GeometryFitnessStatus.ACCEPTABLE:
        status = CameraMatchingStatus.POOR
    return CameraMatchingResult(status=status, assignment=search.best.camera_indices, fitness=fitness, search=search)
