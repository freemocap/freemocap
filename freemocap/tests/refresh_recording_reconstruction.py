"""Refresh a prepared recording's model outputs from saved 3D keypoints."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from filelock import FileLock
import pyarrow.compute as pc
import pyarrow.parquet as pq

from freemocap.core.pipeline.posthoc.processing_request import ProcessingStage
from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.recording.data_descriptors.recording_descriptor import RecordingMetadata, RunDescriptor
from freemocap.core.recording.data_descriptors.recording_model import RecordedModel
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.recording.parquet_storage.parquet_writer import publish_recording, recording_write_lock
from freemocap.core.recording.result_processing.saved_reconstruction import (
    SavedPointPolicy, SavedReconstructionRequest, read_saved_reconstruction,
)
from freemocap.core.recording.sample_encoding.channel_series import SeriesSampling
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionRecording, ReconstructionSourceDefinition, model_source_name,
)
from freemocap.core.recording.sample_encoding.spatial_points import SpatialReference
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.prepare_recording_dataset import file_digest, software_identity, validate_parquet


def refresh_reconstruction(structure, bundle):
    """Replace one model atomically; preserve input rows, other models and runs.

    Restricted to one sensor group for this model because model definitions are
    run-wide. No new run is appended. Publication validates every output row.
    """
    path = structure.data_parquet_path
    before = file_digest(path)
    metadata = read_metadata(path=path)
    run_id = metadata.selected_run_id
    run = metadata.runs[run_id]
    source = model_source_name(bundle.model_id)
    groups = {c.sensor_group for c in run.channels if c.source == source} | {
        f.sensor_group for f in run.scale_fits if f.source == source
    }
    if len(groups) != 1:
        raise ValueError("Refresh requires exactly one sensor group for the model")
    group = next(iter(groups))
    if any(s.channel.source == source for s in run.static_channels):
        raise ValueError("Refresh does not support static model channels")
    definition = ReconstructionSourceDefinition.model_validate(run.sources[source].definition)
    loaded = read_saved_reconstruction(SavedReconstructionRequest(
        structure=structure, run_id=run_id, sensor_group=group,
        point_source=definition.tracker, model_id=bundle.model_id,
        point_policy=SavedPointPolicy.IDENTITY if definition.point_kind == ChannelKind.RAW_KEYPOINTS_3D else SavedPointPolicy.FILTERED,
        compute_center_of_mass=any(c.source == source and c.kind == ChannelKind.DERIVED_POINTS for c in run.channels),
    ))
    if bundle.detector_type != run.models[bundle.model_id].detector_type:
        raise ValueError("Replacement model must use the saved detector")
    result = reconstruct_skeletons_for_recording(replace(
        loaded.numerical_input, bundles=(bundle,), timing=PosthocTimingReport(),
    ))[bundle.model_id]
    if len(result.frames) != len(loaded.points.frames):
        raise ValueError("Reconstruction changed the saved frame count")
    recording = ReconstructionRecording(
        sensor_group=group,
        reference=SpatialReference.model_validate(run.reference_frames[loaded.points.channel.reference_frame]),
        definition=ReconstructionSourceDefinition.from_bundle(
            bundle, tracker_source=definition.tracker, point_kind=definition.point_kind,
        ), result=result,
    )
    invalidated = {ProcessingStage.SCALE_FIT, ProcessingStage.RECONSTRUCTION, ProcessingStage.BIOMECHANICS}
    updated_run = RunDescriptor.model_validate({
        **run.model_dump(),
        "models": {**run.models, bundle.model_id: RecordedModel.from_bundle(bundle)},
        "sources": {**run.sources, source: recording.definition.to_source()},
        "reference_frames": {**run.reference_frames, **recording.reference_frames()},
        "channels": tuple(c for c in run.channels if c.source != source) + tuple(recording.channels()),
        "scale_fits": tuple(f for f in run.scale_fits if f.source != source) + (recording.to_scale_fit(),),
        "checkpoints": tuple(c for c in run.checkpoints if not (c.sensor_group == group and c.stage in invalidated)),
    })
    updated = RecordingMetadata.model_validate({
        **metadata.model_dump(), "runs": {**metadata.runs, run_id: updated_run},
    })

    def batches():
        with pq.ParquetFile(path) as parquet:
            for batch in parquet.iter_batches(batch_size=65536):
                selected = pc.and_(pc.equal(batch.column("run_id"), run_id), pc.equal(batch.column("source"), source))
                retained = batch.filter(pc.invert(selected)).replace_schema_metadata(None)
                if retained.num_rows:
                    yield retained
        sampling = SeriesSampling(frame_numbers=loaded.points.frames, timestamps_s=loaded.points.timestamps_s, run_id=run_id)
        for series in recording.series():
            yield from series.batches(sampling)

    with recording_write_lock(structure=structure):
        if file_digest(path) != before:
            raise RuntimeError("Recording changed during reconstruction; nothing published")
        publish_recording(structure=structure, metadata=updated, batches=batches())
    return {"input_sha256": before, "output_sha256": file_digest(path),
            "frames": len(result.frames), "model_id": bundle.model_id,
            "method": "Current mapping and reconstruction from saved 3D points; no detection, calibration, triangulation or refiltering"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", type=Path, default=Path.home() / "freemocap_data/testing/prepared")
    parser.add_argument("--dataset", choices=("test", "sample"), default="test")
    args = parser.parse_args()
    root = args.prepared_root.resolve() / f"freemocap_{args.dataset}_data"
    with FileLock(str(root / "prepare.lock"), timeout=0):
        marker = root / "ready.json"
        ready = json.loads(marker.read_text(encoding="utf-8"))
        folder = Path(ready["recording"]).resolve()
        if not folder.is_relative_to(root):
            raise ValueError("Prepared recording escapes its dataset directory")
        structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
        if file_digest(structure.data_parquet_path) != ready["result"]["validation"]["parquet_sha256"]:
            raise ValueError("Prepared recording no longer matches ready.json")
        calibration = folder / ready["result"]["calibration_filename"]
        if file_digest(calibration) != ready["result"]["calibration_sha256"]:
            raise ValueError("Prepared calibration no longer matches ready.json")
        metadata = read_metadata(path=structure.data_parquet_path)
        model = metadata.runs[metadata.selected_run_id].models["standard_human"]
        report = refresh_reconstruction(structure, build_standard_human_bundle(detector_type=model.detector_type))
        ready["result"]["validation"] = validate_parquet(folder, expected_frames=report["frames"])
        # Keep original full-pipeline identity; this is only a reconstruction refresh.
        ready["reconstruction_refresh"] = {**report, "software": software_identity()}
        temporary = marker.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(ready, indent=2), encoding="utf-8")
        temporary.replace(marker)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
