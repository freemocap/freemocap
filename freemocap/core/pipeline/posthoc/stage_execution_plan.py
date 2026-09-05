"""Validate reusable checkpoints and invalidate descendants before processing."""

from dataclasses import dataclass
import hashlib
import json


from freemocap.core.pipeline.posthoc.processing_request import (
    ProcessingRequest,
    ProcessingStage,
    STAGE_ORDER,
)
from freemocap.core.recording.recording_metadata import RecordingMetadata, RunDescriptor
from freemocap.core.pipeline.posthoc.execution_inputs import CameraExecutionInputs
from freemocap.core.pipeline.posthoc.stage_dependencies import (
    dependency_closure,
    stage_dependencies,
)


@dataclass(frozen=True, slots=True)
class StageExecutionPlan:
    base_run_id: int
    target_run_id: int
    sensor_groups: tuple[str, ...]
    execute: tuple[ProcessingStage, ...]
    invalidate: tuple[ProcessingStage, ...]


def stage_signature(
    *,
    inputs: dict[str, object],
    settings: dict[str, object],
    algorithm_version: str,
) -> str:
    """Identify the resolved inputs and algorithm that produced a checkpoint."""
    if not algorithm_version:
        raise ValueError("A stage signature requires an algorithm version")
    payload = json.dumps(
        dict(inputs=inputs, settings=settings, algorithm_version=algorithm_version),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_execution_plan(
    *,
    request: ProcessingRequest,
    metadata: RecordingMetadata,
    signatures: dict[str, dict[ProcessingStage, str]],
    inputs: dict[str, CameraExecutionInputs],
) -> StageExecutionPlan:
    """Signatures include resolved stage settings and all relevant upstream inputs."""
    base = metadata.runs[request.base_run_id]
    if not set(request.sensor_groups).issubset(base.sensor_groups):
        raise ValueError("Requested sensor group is absent from the base run")
    stop = STAGE_ORDER.index(request.stop_stage)
    dependencies = stage_dependencies()
    descendants = {
        stage
        for stage in STAGE_ORDER
        if request.start_stage
        in dependency_closure(stages={stage}, dependencies=dependencies)
    }
    execute = tuple(stage for stage in STAGE_ORDER[: stop + 1] if stage in descendants)
    if request.stop_stage not in execute:
        raise ValueError("stop_stage must depend on start_stage")
    prerequisites = set().union(*(dependencies[stage] for stage in execute)) - set(
        execute
    )
    saved = {
        (item.sensor_group, item.stage): item.signature for item in base.checkpoints
    }
    for group in request.sensor_groups:
        inputs[group].validate_for(execute)
        for stage in STAGE_ORDER:
            if stage not in prerequisites:
                continue
            expected = signatures[group][stage]
            if saved.get((group, stage)) != expected:
                raise ValueError(
                    f"Restart at {stage.value}: {group} checkpoint missing or inputs changed"
                )
    return StageExecutionPlan(
        base_run_id=request.base_run_id,
        target_run_id=max(metadata.runs) + 1 if request.keep else request.base_run_id,
        sensor_groups=request.sensor_groups,
        execute=execute,
        invalidate=tuple(stage for stage in STAGE_ORDER if stage in descendants),
    )


def retained_run(*, base: RunDescriptor, plan: StageExecutionPlan) -> RunDescriptor:
    """Remove invalid dynamic/static outputs and their completion records together."""
    data = base.model_dump()
    data["scale_fits"] = [
        fit.model_dump()
        for fit in base.scale_fits
        if fit.sensor_group not in plan.sensor_groups
        or ProcessingStage.SCALE_FIT not in plan.invalidate
    ]
    data["channels"] = [
        channel.model_dump()
        for channel in base.channels
        if channel.sensor_group not in plan.sensor_groups
        or channel.stage not in plan.invalidate
    ]
    data["static_channels"] = [
        item.model_dump()
        for item in base.static_channels
        if item.channel.sensor_group not in plan.sensor_groups
        or item.channel.stage not in plan.invalidate
    ]
    data["checkpoints"] = [
        item.model_dump()
        for item in base.checkpoints
        if item.sensor_group not in plan.sensor_groups
        or item.stage not in plan.invalidate
    ]
    return RunDescriptor.model_validate(data)
