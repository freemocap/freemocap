"""Scientific dependencies used for checkpoint reuse and invalidation."""

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage


def stage_dependencies(
    *,
    solve_calibration: bool,
) -> dict[ProcessingStage, frozenset[ProcessingStage]]:
    stage = ProcessingStage
    return {
        stage.TIMING: frozenset(),
        stage.OBSERVATIONS: frozenset({stage.TIMING}),
        stage.CALIBRATION: frozenset({stage.OBSERVATIONS})
        if solve_calibration
        else frozenset(),
        stage.TRIANGULATION: frozenset({stage.OBSERVATIONS, stage.CALIBRATION}),
        stage.FILTERING: frozenset({stage.TRIANGULATION, stage.TIMING}),
        stage.SCALE_FIT: frozenset({stage.FILTERING}),
        stage.RECONSTRUCTION: frozenset({stage.FILTERING, stage.SCALE_FIT}),
        stage.BIOMECHANICS: frozenset(
            {stage.RECONSTRUCTION, stage.SCALE_FIT, stage.TIMING}
        ),
    }


def dependency_closure(
    *,
    stages: set[ProcessingStage],
    dependencies: dict[ProcessingStage, frozenset[ProcessingStage]],
) -> set[ProcessingStage]:
    """Return stages and all their transitive prerequisites."""
    result = set(stages)
    pending = list(stages)
    while pending:
        for dependency in dependencies[pending.pop()]:
            if dependency not in result:
                result.add(dependency)
                pending.append(dependency)
    return result
