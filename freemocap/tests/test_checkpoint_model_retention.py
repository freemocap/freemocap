"""Changing reconstruction placement must preserve retained numerical evidence."""

import pytest

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.pipeline.posthoc.stage_execution_plan import StageExecutionPlan, retained_run
from freemocap.core.reconstruction.recording_fit import RecordingFitInputs
from freemocap.core.recording.data_descriptors.recording_descriptor import (
    Channel, RecordingMetadata, RunDescriptor, SensorGroup, Source, SourceKind, StaticChannel,
)
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.data_descriptors.scale_fit import RecordingScaleFit
from freemocap.core.recording.parquet_storage import checkpoint_publication as publication
from freemocap.core.recording.result_processing.input_signatures import definition_signature
from freemocap.core.recording.sample_encoding.reconstruction_samples import model_source_name
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.system.recording_structure.recording_structure import RecordingStructure


@pytest.fixture
def model_context():
    bundle = build_standard_human_bundle(detector_type="rtmpose", anchor_segment_name="pelvis")
    model = RecordedModel.from_bundle(bundle)
    source = model_source_name(model.model_id)
    fit = RecordingScaleFit(sensor_group="selected_group", source=source, reference_frame="world_frame", units="mm",
        fit=None, inputs=RecordingFitInputs(algorithm_version=1, keypoint_names=model.tracker_keypoint_names,
            points="0" * 64, model=definition_signature(model.model_dump(exclude={"anchor_segment_name"}))))
    run = RunDescriptor(sensor_groups={name: SensorGroup(clock_description=name, sample_count=1)
                                      for name in ("selected_group", "other_group")},
        sources={source: Source(kind=SourceKind.INSTANCE, definition={"model_id": model.model_id})},
        reference_frames={"world_frame": {"units": "mm"}}, models={model.model_id: model},
        processing={}, channels=(), scale_fits=(fit,))
    channel = Channel(sensor_group="selected_group", source=source, reference_frame="world_frame",
        kind="SEGMENT_ORIGINS", names=(next(iter(bundle.skeleton.segments)),),
        components={"x": "mm", "y": "mm", "z": "mm"}, stage=ProcessingStage.RECONSTRUCTION)
    return run, channel


def _publish_changed_model(tmp_path, monkeypatch, run, *, model_updates, invalidate=True):
    metadata = RecordingMetadata(recording_id="model_contract", selected_run_id=0, runs={0: run})
    plan = StageExecutionPlan(base_run_id=0, target_run_id=0, sensor_groups=("selected_group",),
        execute=(ProcessingStage.RECONSTRUCTION,),
        invalidate=(ProcessingStage.RECONSTRUCTION,) if invalidate else ())
    retained = retained_run(base=run, plan=plan)
    model_id, model = next(iter(retained.models.items()))
    proposed = RecordedModel.model_validate({**model.model_dump(), **model_updates})
    result = RunDescriptor.model_validate({**retained.model_dump(), "models": {model_id: proposed}})
    calls = []
    monkeypatch.setattr(publication, "read_metadata", lambda **kwargs: metadata)
    monkeypatch.setattr(publication, "publish_recording", lambda **kwargs: calls.append(kwargs))
    structure = RecordingStructure(base_directory=tmp_path, recording_name="model_contract")
    published = publication.publish_checkpoint(structure=structure, metadata=metadata, plan=plan,
        result=result, computed_batches=())
    assert len(calls) == 1
    assert published.runs[0].scale_fits == run.scale_fits
    return published


def test_fit_only_retention_allows_anchor_change(tmp_path, monkeypatch, model_context):
    run, _ = model_context
    published = _publish_changed_model(tmp_path, monkeypatch, run, model_updates={"anchor_segment_name": "skull"})
    assert published.runs[0].models["standard_human"].anchor_segment_name == "skull"


@pytest.mark.parametrize("model_updates", [
    {"scale_reference_name": "different_reference"},
    {"tracker_keypoint_names": ("different_keypoint",)},
])
def test_fit_only_retention_rejects_scientific_model_changes(tmp_path, monkeypatch, model_context, model_updates):
    run, _ = model_context
    with pytest.raises(ValueError, match="models used by retained scale fits"):
        _publish_changed_model(tmp_path, monkeypatch, run, model_updates=model_updates)


def test_fit_only_retention_preserves_definition_order(tmp_path, monkeypatch, model_context):
    run, _ = model_context
    masses = run.models["standard_human"].segment_masses
    with pytest.raises(ValueError, match="models used by retained scale fits"):
        _publish_changed_model(tmp_path, monkeypatch, run,
            model_updates={"segment_masses": dict(reversed(tuple(masses.items())))})


@pytest.mark.parametrize("retained_kind", ["dynamic_channel", "static_channel", "other_group"])
def test_retained_output_rejects_anchor_change(tmp_path, monkeypatch, model_context, retained_kind):
    run, channel = model_context
    data = run.model_dump()
    invalidate = retained_kind == "other_group"
    if retained_kind == "other_group":
        channel = channel.model_copy(update={"sensor_group": "other_group"})
    if retained_kind == "static_channel":
        data["static_channels"] = (StaticChannel(channel=channel,
            values={channel.names[0]: {component: 0.0 for component in channel.components}}),)
    else:
        data["channels"] = (channel,)
    run = RunDescriptor.model_validate(data)
    with pytest.raises(ValueError, match="models used by retained outputs"):
        _publish_changed_model(tmp_path, monkeypatch, run,
            model_updates={"anchor_segment_name": "skull"}, invalidate=invalidate)
