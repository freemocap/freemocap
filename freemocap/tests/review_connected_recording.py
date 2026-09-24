"""Review current skeleton math on saved 3D evidence; never publish recording changes."""

import argparse
from dataclasses import replace
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
import subprocess

import numpy as np
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion
from skellyforge.core.math.geometry.spatial_vectors import Point
from skellyforge.core.skeleton.chain.synthesis import synthesize_fitted_pose

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


def connected_geometry(bundle, fit, frame):
    """Only connect finite poses with a complete observed ancestor path."""
    if frame is None:
        return {}, {}
    parents = bundle.rest_pose.parents
    root = bundle.rest_pose.root_segment_name
    available = {
        name for name, segment in bundle.skeleton.segments.items()
        if name in frame.segment_rotations_world
        and np.isfinite(frame.segment_rotations_world[name]).all()
        and segment.frame_definition.origin_point_name in frame.landmarks
        and np.isfinite(frame.landmarks[segment.frame_definition.origin_point_name]).all()
    }
    selected = set()
    def include(name):
        if name not in available:
            return False
        parent = parents[name]
        if parent is not None and not include(parent):
            return False
        selected.add(name)
        return True
    for name in available:
        include(name)
    if root not in selected:
        return {}, {}
    rotations = {name: RotationQuaternion.from_array(array=frame.segment_rotations_world[name]) for name in selected}
    _, origins, _ = synthesize_fitted_pose(
        skeleton=bundle.skeleton, fit=fit, segment_names=frozenset(selected),
        root_origin=Point.from_array(values=frame.landmarks[bundle.skeleton.segments[root].frame_definition.origin_point_name]),
        root_world_orientation=rotations[root],
        segment_relative_orientations={name: rotations[parents[name]].inverse() * rotations[name]
                                       for name in selected if name != root},
    )
    return origins, rotations


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
    if len(result.frames) != len(timestamps):
        raise ValueError("Reconstruction must preserve the saved frame count")
    fit = result.scale_fit
    frames = []
    coverage = dict.fromkeys(bundle.skeleton.segments, 0)
    for index, frame in enumerate(result.frames):
        connected, _ = connected_geometry(bundle, fit, frame)
        points = {name: point for name, point in zip(loaded.points.channel.names, loaded.points.values[index], strict=True)
                  if np.isfinite(point).all()}
        mapped = bundle.landmark_mapping.apply(tracker_positions=points)
        segments = {}
        if frame is not None:
            for name, quaternion in frame.segment_rotations_world.items():
                segment = bundle.skeleton.segments[name]
                origin = frame.landmarks.get(segment.frame_definition.origin_point_name)
                if origin is None or not np.isfinite(origin).all() or not np.isfinite(quaternion).all():
                    continue
                q = RotationQuaternion.from_array(array=quaternion)
                local = bundle.skeleton.landmarks[segment.frame_definition.primary_point_name].local_position.array * fit.segment_scales[name]
                direction = q.rotate_vector(vector=local)
                connected_origin = connected[name].array if name in connected else None
                segments[name] = dict(origin=origin.tolist(), end=(origin + direction).tolist(),
                    connected_origin=connected_origin.tolist() if connected_origin is not None else None,
                    connected_end=(connected_origin + direction).tolist() if connected_origin is not None else None,
                    axes=q.to_rotation_matrix().T.tolist(),
                    shift_mm=float(np.linalg.norm(connected_origin - origin)) if connected_origin is not None else None)
                coverage[name] += name in connected
        frames.append(dict(number=loaded.points.frames[index], time=loaded.points.timestamps_s[index],
                           shoulder_keypoints={n: points[n].tolist() for n in ('left_shoulder', 'right_shoulder') if n in points},
                           points={n:p.tolist() for n,p in mapped.items() if np.isfinite(p).all()}, segments=segments))
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
