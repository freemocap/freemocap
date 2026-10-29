"""Review current skeleton math on saved 3D evidence; never publish recording changes."""

import argparse
from dataclasses import replace
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import subprocess

import numpy as np
from skellyforge.core.math.geometry.rotation_quaternion import quaternions_to_rotation_matrices
from skellyforge.core.skeleton.chain.anchored_batch import AnchoredSkeletonGeometry

from freemocap.core.recording.playback_queries import recording_view
from freemocap.core.recording.sample_encoding.reconstruction_samples import ReconstructionSourceDefinition, model_source_name
from freemocap.core.recording.result_processing.saved_reconstruction import SavedPointPolicy, SavedReconstructionRequest, read_saved_reconstruction
from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording
from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.types.channel_kind import ChannelKind
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def connected_geometry(bundle, fit, origins, rotations, present):
    """Connect all frame poses with complete root paths using Forge batch geometry."""
    geometry = AnchoredSkeletonGeometry.from_skeleton(skeleton=bundle.skeleton, fit=fit,
        anchor_segment_name=bundle.rest_pose.root_segment_name)
    selected = np.zeros_like(present)
    selected[:, geometry.anchor_index] = present[:, geometry.anchor_index]
    for parents, children, _, _ in geometry.traversal_levels:
        selected[:, children] = selected[:, parents] & present[:, children]
    return geometry.positions(world_orientations=rotations, segment_present=selected,
        anchor_origins=origins[:, geometry.anchor_index])


def build_review(path, sensor_group=None):
    path = path.resolve()
    before = file_digest(path)
    with recording_view(path) as view:
        run_id = view.metadata.selected_run_id
        run = view.metadata.runs[run_id]
        source = model_source_name("standard_human")
        definition = ReconstructionSourceDefinition.model_validate(run.sources[source].definition)
        candidates = [c for c in run.channels if c.source == source and c.kind == ChannelKind.ROTATIONS_WORLD
                      and (sensor_group is None or c.sensor_group == sensor_group)]
        if len(candidates) != 1:
            raise ValueError("Choose one reconstruction sensor group with --sensor-group")
        group = candidates[0].sensor_group
        detector = run.models["standard_human"].detector_type
        revision = view.revision
    loaded = read_saved_reconstruction(SavedReconstructionRequest(
        structure=RecordingStructure(base_directory=path.parent.parent, recording_name=path.parent.name),
        run_id=run_id, sensor_group=group, point_source=definition.tracker, model_id="standard_human",
        point_policy=SavedPointPolicy.IDENTITY if definition.point_kind == ChannelKind.RAW_KEYPOINTS_3D else SavedPointPolicy.FILTERED,
        compute_center_of_mass=False,
    ))
    if set(loaded.points.channel.components.values()) != {"mm"}:
        raise ValueError("Review requires saved point coordinates in millimetres")
    timestamps = np.asarray(loaded.points.timestamps_s)
    if not len(timestamps) or not np.isfinite(timestamps).all() or not (np.diff(timestamps) > 0).all():
        raise ValueError("Review requires finite, strictly increasing saved timestamps")
    bundle = build_standard_human_bundle(detector_type=detector)
    result = reconstruct_skeletons_for_recording(replace(
        loaded.numerical_input, bundles=(bundle,), timing=PosthocTimingReport()))[bundle.model_id]
    if result.scale_fit is None:
        raise ValueError("Current reconstruction produced no scale fit")
    if result.frame_count != len(timestamps):
        raise ValueError("Reconstruction must preserve the saved frame count")
    fit = result.scale_fit
    rotation_tensor = result.channel_tensor(ChannelKind.ROTATIONS_WORLD)
    landmark_tensor = result.channel_tensor(ChannelKind.LANDMARKS_3D)
    mapped_tensor = result.channel_tensor(ChannelKind.MAPPED_KEYPOINTS_3D)
    segment_names = rotation_tensor.tensor_layout.axes[1].identifiers
    landmark_names = landmark_tensor.tensor_layout.axes[1].identifiers
    origin_columns = [landmark_names.index(bundle.skeleton.segments[name].frame_definition.origin_point_name) for name in segment_names]
    origins = landmark_tensor.data_values[:, origin_columns]
    rotations = rotation_tensor.data_values
    present = rotation_tensor.companion_values("entry_presence").all(axis=-1) & np.isfinite(origins).all(axis=-1)
    connected = connected_geometry(bundle, fit, origins, rotations, present)
    component_count = origins.shape[-1]
    matrices = np.full((*present.shape, component_count, component_count), np.nan)
    matrices[present] = quaternions_to_rotation_matrices(quaternions=rotations[present])
    local_vectors = np.asarray([bundle.skeleton.landmarks[bundle.skeleton.segments[name].frame_definition.primary_point_name].local_position.array
                               * fit.segment_scales[name] for name in segment_names])
    directions = np.einsum("fsij,sj->fsi", matrices, local_vectors)
    ends = origins + directions
    connected_ends = connected.segment_origins + directions
    shifts = np.linalg.norm(connected.segment_origins - origins, axis=-1)
    mapped_present = mapped_tensor.companion_values("entry_presence").all(axis=-1)
    shoulder_columns = {name: loaded.points.channel.names.index(name) for name in ('left_shoulder', 'right_shoulder') if name in loaded.points.channel.names}
    coverage = {name: int(connected.segment_present[:, column].sum()) for column, name in enumerate(segment_names)}
    frames = []
    # Numerical work is complete. This loop only serializes the HTML review's JSON schema.
    for index in range(result.frame_count):
        segments = {}
        for column in np.flatnonzero(present[index]):
            available = connected.segment_present[index, column]
            segments[segment_names[column]] = dict(origin=origins[index, column].tolist(), end=ends[index, column].tolist(),
                connected_origin=connected.segment_origins[index, column].tolist() if available else None,
                connected_end=connected_ends[index, column].tolist() if available else None,
                axes=matrices[index, column].T.tolist(), shift_mm=float(shifts[index, column]) if available else None)
        frames.append(dict(number=loaded.points.frames[index], time=loaded.points.timestamps_s[index],
            shoulder_keypoints={name: loaded.points.values[index, column].tolist() for name, column in shoulder_columns.items()
                                if np.isfinite(loaded.points.values[index, column]).all()},
            points={landmark_names[column]: mapped_tensor.data_values[index, column].tolist()
                    for column in np.flatnonzero(mapped_present[index])}, segments=segments))
    if file_digest(path) != before:
        raise RuntimeError("Source changed during review generation; discard output")
    return dict(frames=frames, coverage=coverage, parents=dict(bundle.rest_pose.parents),
        provenance=dict(path=str(path), sha256=before, revision=revision, run_id=run_id, sensor_group=group,
            input_channel=str(loaded.points.channel.kind), reference_frame=loaded.points.channel.reference_frame,
            units="mm", fitted_scale_mm=fit.fitted_scale,
            method="Current mapping, recording-wide scale fit and chronological reconstruction from saved 3D points; no detection, calibration, triangulation or publication",
            packages={name:json.loads(distribution(name).read_text("direct_url.json") or "{}") for name in ("skellyforge", "skellytracker")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--sensor-group")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.suffix.lower() != ".html" or args.output.resolve() == args.parquet.resolve():
        raise ValueError("Output must be a separate .html review artifact")
    data = build_review(args.parquet, args.sensor_group)
    ui_root = Path(__file__).resolve().parents[2] / "freemocap-ui"
    code = "process.stdout.write(require('esbuild').buildSync({entryPoints:['dev/connected_recording_review.js'],bundle:true,write:false,minify:true,format:'iife'}).outputFiles[0].text)"
    javascript = subprocess.run(["node", "-e", code], cwd=ui_root, check=True, capture_output=True, text=True).stdout
    payload = json.dumps(data, allow_nan=False).replace("<", "\\u003c")
    template = (Path(__file__).with_name("connected_recording_review.html")).read_text(encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace("__DATA__", payload).replace("__JAVASCRIPT__", javascript), encoding="utf-8")
    print(json.dumps(dict(output=str(args.output.resolve()), frames=len(data['frames']), coverage=data['coverage']), indent=2))


if __name__ == "__main__":
    main()
