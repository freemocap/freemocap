"""Placement changes invalidate derived results while retaining valid fitted inputs."""
import pytest

from freemocap.core.pipeline.posthoc.execution_inputs import CameraExecutionInputs
from freemocap.core.pipeline.posthoc.processing_request import ProcessingRequest, ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import build_execution_plan, retained_run
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.pipeline.posthoc.saved_stage_processing import run_saved_numerical_stages
from freemocap.core.pipeline.dataflow.saved_spatial_source import load_saved_spatial_source
from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
from freemocap.core.recording.data_descriptors.recording_descriptor import StageCheckpoint
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.result_processing import input_signatures, saved_reconstruction
from freemocap.core.recording.result_processing.reconstruction_completion import reconstruction_checkpoints
from freemocap.core.recording.result_processing.observation_publication import publish_posthoc_observations
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.tests.test_reconstruction_checkpoints import publication
from freemocap.tests.test_saved_reconstruction import saved_request


def signature_map(checkpoints):
    return {item.stage: item.signature for item in checkpoints}


def assert_only_derived_signatures_change(old, current):
    for stage in (ProcessingStage.FILTERING, ProcessingStage.SCALE_FIT):
        assert old[stage] == current[stage]
    for stage in (ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS):
        assert old[stage] != current[stage]


def test_connected_checkpoint_rejected_for_biomechanics_but_fit_reused_for_reconstruction(publication, monkeypatch):
    assert input_signatures.RECONSTRUCTION_STAGE_VERSION == 2
    with monkeypatch.context() as legacy:
        legacy.setattr(input_signatures, "RECONSTRUCTION_STAGE_VERSION", 1)
        old = signature_map(reconstruction_checkpoints(request=publication, timestamps_s=(0., 1 / 30)))
    current = signature_map(reconstruction_checkpoints(request=publication, timestamps_s=(0., 1 / 30)))
    assert_only_derived_signatures_change(old, current)
    metadata = publish_posthoc_observations(publication)
    fit = publication.reconstructions[0].to_scale_fit()
    assert fit.fit is not None
    old[ProcessingStage.TIMING] = current[ProcessingStage.TIMING] = "timing"
    base = metadata.runs[0].model_copy(update={
        "scale_fits": (fit,),
        "checkpoints": tuple(StageCheckpoint(sensor_group="mocap", stage=stage, signature=value)
                             for stage, value in old.items()),
    })
    metadata = metadata.model_copy(update={"runs": {0: base}})
    arguments = dict(metadata=metadata, signatures={"mocap": current},
                     inputs={"mocap": CameraExecutionInputs(camera_ids=(), geometry=())})
    with pytest.raises(ValueError, match="Restart at reconstruction"):
        build_execution_plan(request=ProcessingRequest(sensor_groups=("mocap",),
            start_stage=ProcessingStage.BIOMECHANICS, stop_stage=ProcessingStage.BIOMECHANICS), **arguments)
    plan = build_execution_plan(request=ProcessingRequest(sensor_groups=("mocap",),
        start_stage=ProcessingStage.RECONSTRUCTION, stop_stage=ProcessingStage.BIOMECHANICS), **arguments)
    assert ProcessingStage.SCALE_FIT not in plan.execute
    assert {ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS}.issubset(plan.invalidate)
    retained = retained_run(base=base, plan=plan)
    assert retained.scale_fits == (fit,)
    assert not {ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS}.intersection(signature_map(retained.checkpoints))


@pytest.mark.parametrize("route", ["current", "typed_dataflow"])
def test_both_resume_writers_replace_legacy_derived_checkpoints_only(saved_request, monkeypatch, route):
    def process(start):
        config = PosthocMocapPipelineConfig(pipeline_implementation=route,
            base_run_id=3, sensor_group="mocap", start_stage=start, export_to_blender=False)
        if route == "current":
            run_saved_numerical_stages(structure=saved_request.structure, config=config,
                                      reporter=TaskProgressReporter.noop())
        else:
            source = load_saved_spatial_source(path=saved_request.structure.full_path, config=config)
            graph, handlers = build_saved_spatial_pipeline(source=source, config=config)
            result = execute_recording_graph(graph=graph, handlers=handlers)
            assert result.complete, result.failure_tracebacks
        return read_metadata(path=saved_request.structure.data_parquet_path).runs[3]
    with monkeypatch.context() as legacy:
        legacy.setattr(input_signatures, "RECONSTRUCTION_STAGE_VERSION", 1)
        old = process("filtering")
    current = process("reconstruction")
    assert_only_derived_signatures_change(signature_map(old.checkpoints), signature_map(current.checkpoints))
    assert current.scale_fits == old.scale_fits
    assert current.processing["mocap"]["filtering"] == old.processing["mocap"]["filtering"]


def test_saved_input_fingerprint_includes_stage_version_without_invalidating_fit(saved_request):
    loaded = saved_reconstruction.read_saved_reconstruction(saved_request)
    common = dict(points=loaded.signatures.points, model=loaded.signatures.model,
        fit=loaded.signatures.fit, point_policy=saved_request.point_policy,
        compute_center_of_mass=saved_request.compute_center_of_mass)
    assert loaded.signatures.reconstruction != input_signatures.definition_signature(common)
    assert loaded.signatures.reconstruction != input_signatures.definition_signature(dict(version=1, **common))
    assert loaded.signatures.reconstruction == input_signatures.definition_signature(
        dict(version=input_signatures.RECONSTRUCTION_STAGE_VERSION, **common))
    assert loaded.fit.inputs == loaded.numerical_input.fit_inputs(loaded.numerical_input.bundles[0])
