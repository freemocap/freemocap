"""Read-only evidence for secondary exports; never acquires or processes recordings."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
from skellyforge.core.math.geometry.rotation_quaternion import RotationQuaternion

from freemocap.core.recording.playback_queries import recording_view
from freemocap.core.recording.sample_encoding.reconstruction_samples import (
    ReconstructionSourceDefinition, model_source_name,
)
from freemocap.core.types.channel_kind import ChannelKind


def statistics(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not values.size:
        return {"count": 0, "rms": None, "p95": None, "max": None}
    return {"count": int(values.size), "rms": float(np.sqrt(np.mean(values ** 2))),
            "p95": float(np.percentile(values, 95)), "max": float(values.max())}


def measure_hierarchy(parents, positions, rotations, fitted_offsets):
    """Compare exact moving offsets, per-edge mean offsets, and fitted rest offsets.

    Matrices map local axes to world axes. Missing ancestors invalidate FK all the
    way down that branch. Mean offsets minimize each edge's squared translation
    residual, not the whole hierarchy's FK error; they are not a proposed rig fit.
    """
    if set(parents) != set(positions) or set(parents) != set(rotations):
        raise ValueError("Pose arrays must cover exactly the declared hierarchy")
    order = []
    pending = dict(parents)
    while pending:
        ready = [name for name, parent in pending.items() if parent is None or parent in order]
        if not ready:
            raise ValueError("Hierarchy contains a cycle or unknown parent")
        for name in ready:
            order.append(name)
            del pending[name]
    exact, mean_fk, fitted_fk, world_fk = {}, {}, {}, {}
    edges = {}
    for name in order:
        parent = parents[name]
        position, rotation = positions[name], rotations[name]
        valid = np.isfinite(position).all(axis=1) & np.isfinite(rotation).all(axis=(1, 2))
        if parent is None:
            exact[name] = np.where(valid[:, None], position, np.nan)
            mean_fk[name] = exact[name].copy()
            fitted_fk[name] = exact[name].copy()
            world_fk[name] = np.where(valid[:, None, None], rotation, np.nan)
            continue
        parent_rotation = rotations[parent]
        inverse = np.swapaxes(parent_rotation, 1, 2)
        offset = np.einsum("tij,tj->ti", inverse, position - positions[parent])
        local_rotation = inverse @ rotation
        pair_valid = valid & np.isfinite(positions[parent]).all(axis=1) & np.isfinite(parent_rotation).all(axis=(1, 2))
        offset[~pair_valid] = np.nan
        local_rotation[~pair_valid] = np.nan
        mean = offset[pair_valid].mean(axis=0) if pair_valid.any() else np.full(3, np.nan)
        world_fk[name] = world_fk[parent] @ local_rotation
        exact[name] = exact[parent] + np.einsum("tij,tj->ti", world_fk[parent], offset)
        mean_fk[name] = mean_fk[parent] + np.einsum("tij,j->ti", world_fk[parent], mean)
        fitted_fk[name] = fitted_fk[parent] + np.einsum("tij,j->ti", world_fk[parent], fitted_offsets[name])
        for result in (exact, mean_fk, fitted_fk):
            result[name][~pair_valid] = np.nan
        edges[name] = {
            "parent": parent,
            "valid_pair_frames": int(pair_valid.sum()),
            "mean_offset_mm": mean.tolist() if pair_valid.any() else None,
            "fitted_rest_offset_mm": np.asarray(fitted_offsets[name]).tolist(),
            "offset_variation_mm": statistics(np.linalg.norm(offset - mean, axis=1)),
            "exact_fk_error_mm": statistics(np.linalg.norm(exact[name] - position, axis=1)),
            "mean_offset_fk_error_mm": statistics(np.linalg.norm(mean_fk[name] - position, axis=1)),
            "fitted_rest_fk_error_mm": statistics(np.linalg.norm(fitted_fk[name] - position, axis=1)),
            "rotation_matrix_error": statistics(np.linalg.norm(world_fk[name] - rotation, axis=(1, 2))),
        }
    return edges


def inspect(path, *, model_id="standard_human", sensor_group=None):
    def digest():
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    before = digest()
    with recording_view(path) as view:
        run_id = view.metadata.selected_run_id
        run = view.metadata.runs[run_id]
        source = model_source_name(model_id)
        definition = ReconstructionSourceDefinition.model_validate(run.sources[source].definition)
        bundle = run.models[model_id].to_bundle()
        parents = definition.segment_parents
        if dict(bundle.rest_pose.parents) != parents:
            raise ValueError("Saved skeleton and reconstruction parent maps disagree")
        kinds = (ChannelKind.SEGMENT_ORIGINS, ChannelKind.ROTATIONS_WORLD)
        channels = [c for c in run.channels if c.source == source and c.kind in kinds
                    and (sensor_group is None or c.sensor_group == sensor_group)]
        if len(channels) != 2 or {c.kind for c in channels} != set(kinds):
            raise ValueError("Select one group with origins and world rotations")
        by_kind = {c.kind: c for c in channels}
        origin_channel = by_kind[ChannelKind.SEGMENT_ORIGINS]
        rotation_channel = by_kind[ChannelKind.ROTATIONS_WORLD]
        if (origin_channel.sensor_group, origin_channel.reference_frame) != (
                rotation_channel.sensor_group, rotation_channel.reference_frame):
            raise ValueError("Origin and rotation contexts differ")
        if dict(origin_channel.components) != dict.fromkeys(("x", "y", "z"), "mm"):
            raise ValueError("This diagnostic requires metric xyz origins in millimeters")
        if dict(rotation_channel.components) != dict.fromkeys(("w", "x", "y", "z"), "1"):
            raise ValueError("This diagnostic requires dimensionless WXYZ rotations")
        fits = [f for f in run.scale_fits if f.source == source and
                f.sensor_group == origin_channel.sensor_group and
                f.reference_frame == origin_channel.reference_frame and f.units == "mm"]
        if len(fits) != 1 or fits[0].fit is None:
            raise ValueError("One saved metric scale fit is required")
        fit = fits[0].fit
        # The stored rest pose resolves branching connect_at landmarks. Apply the
        # parent's fitted scale to its local attachment; lengths alone aren't offsets.
        fitted_offsets = {
            name: bundle.skeleton.landmarks[bundle.rest_pose.connect_ats[name]].local_position.array
                  * fit.segment_scales[parent]
            for name, parent in parents.items() if parent is not None
        }
        rows = {}
        timestamps = {}
        for batch in view.parquet.iter_batches(batch_size=65536):
            mask = pc.and_(pc.equal(batch.column("run_id"), run_id), pc.equal(batch.column("source"), source))
            mask = pc.and_(mask, pc.equal(batch.column("sensor_group"), origin_channel.sensor_group))
            mask = pc.and_(mask, pc.equal(batch.column("reference_frame"), origin_channel.reference_frame))
            mask = pc.and_(mask, pc.or_(pc.equal(batch.column("channel"), kinds[0]),
                                      pc.equal(batch.column("channel"), kinds[1])))
            for row in batch.filter(mask).to_pylist():
                frame, timestamp = row["frame_number"], row["timestamp_s"]
                if not np.isfinite(timestamp) or (frame in timestamps and timestamps[frame] != timestamp):
                    raise ValueError("Invalid or inconsistent frame timestamp")
                timestamps[frame] = timestamp
                key = (row["channel"], frame, row["name"], row["component"])
                if key in rows:
                    raise ValueError("Duplicate scalar sample")
                channel = by_kind[row["channel"]]
                if row["name"] not in parents or row["component"] not in channel.components or row["units"] != channel.components[row["component"]]:
                    raise ValueError("Unexpected sample identity or units")
                rows[key] = np.nan if row["value"] is None else row["value"]
        frames = sorted(timestamps)
        if not frames or len(frames) != run.sensor_groups[origin_channel.sensor_group].sample_count:
            raise ValueError("Frame grid does not match saved group")
        if not np.all(np.diff([timestamps[f] for f in frames]) > 0):
            raise ValueError("Frame timestamps are not strictly increasing")
        positions, rotations = {}, {}
        for name in parents:
            positions[name] = np.array([[rows.get((kinds[0], f, name, c), np.nan)
                                         for c in ("x", "y", "z")] for f in frames])
            quaternions = np.array([[rows.get((kinds[1], f, name, c), np.nan)
                                    for c in ("w", "x", "y", "z")] for f in frames])
            rotations[name] = np.full((len(frames), 3, 3), np.nan)
            for index, quaternion in enumerate(quaternions):
                if np.isfinite(quaternion).all():
                    if not np.isclose(np.linalg.norm(quaternion), 1., atol=1e-6, rtol=0.):
                        raise ValueError("Saved rotation is not unit length")
                    rotations[name][index] = RotationQuaternion.from_array(array=quaternion).to_rotation_matrix()
        edges = measure_hierarchy(parents, positions, rotations, fitted_offsets)
        report = {
            "recording": view.metadata.recording_id, "source_sha256": before,
            "revision": view.revision, "run_id": run_id, "model_id": model_id,
            "sensor_group": origin_channel.sensor_group, "reference_frame": origin_channel.reference_frame,
            "frames": len(frames), "time_range_s": [timestamps[frames[0]], timestamps[frames[-1]]],
            "fitted_model_scale_mm": fit.fitted_scale, "segments": len(parents),
            "offset_policy": "saved connect_at landmark times parent fitted scale; also per-edge mean observed offset",
            "edges": edges,
        }
    if digest() != before:
        raise RuntimeError("Source changed during inspection; discard this report")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--model-id", default="standard_human")
    parser.add_argument("--sensor-group")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--reconstruct-current", action="store_true",
                        help="Refit/reconstruct saved 3D inputs with installed definitions; never run detectors or publish Parquet")
    args = parser.parse_args()
    report = inspect(args.parquet, model_id=args.model_id, sensor_group=args.sensor_group)
    if args.reconstruct_current:
        report = reconstruct_current(args.parquet, report)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        if args.output.resolve() == args.parquet.resolve():
            raise ValueError("Report must not overwrite source Parquet")
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def reconstruct_current(path, previous):
    """Compare current reconstruction to the stored result on identical 3D evidence."""
    from dataclasses import replace
    from importlib.metadata import distribution

    from freemocap.core.reconstruction.posthoc_reconstruction import reconstruct_skeletons_for_recording
    from freemocap.core.reconstruction.posthoc_timing import PosthocTimingReport
    from freemocap.core.recording.result_processing.saved_reconstruction import (
        SavedPointPolicy, SavedReconstructionRequest, read_saved_reconstruction,
    )
    from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
    from freemocap.system.recording_structure.recording_structure import RecordingStructure

    model_id = previous["model_id"]
    with recording_view(path) as view:
        run = view.metadata.runs[previous["run_id"]]
        definition = ReconstructionSourceDefinition.model_validate(run.sources[model_source_name(model_id)].definition)
        detector_type = run.models[model_id].detector_type
    loaded = read_saved_reconstruction(SavedReconstructionRequest(
        structure=RecordingStructure(base_directory=path.parent.parent, recording_name=path.parent.name),
        run_id=previous["run_id"], sensor_group=previous["sensor_group"],
        point_source=definition.tracker, model_id=model_id,
        point_policy=SavedPointPolicy.IDENTITY if definition.point_kind == ChannelKind.RAW_KEYPOINTS_3D else SavedPointPolicy.FILTERED,
        compute_center_of_mass=False,
    ))
    bundle = build_standard_human_bundle(detector_type=detector_type)
    if bundle.model_id != model_id:
        raise ValueError("Current reconstruction comparison supports the standard human only")
    result = reconstruct_skeletons_for_recording(replace(
        loaded.numerical_input, bundles=(bundle,), timing=PosthocTimingReport()))[model_id]
    if result.scale_fit is None:
        raise ValueError("Current reconstruction did not produce a scale fit")
    parents = dict(bundle.rest_pose.parents)
    positions = {name: np.full((len(result.frames), 3), np.nan) for name in parents}
    rotations = {name: np.full((len(result.frames), 3, 3), np.nan) for name in parents}
    for index, frame in enumerate(result.frames):
        if frame is None:
            continue
        for name, segment in bundle.skeleton.segments.items():
            positions[name][index] = frame.landmarks.get(segment.frame_definition.origin_point_name, np.full(3, np.nan))
            if name in frame.segment_rotations_world:
                rotations[name][index] = RotationQuaternion.from_array(array=frame.segment_rotations_world[name]).to_rotation_matrix()
    fitted_offsets = {
        name: bundle.skeleton.landmarks[bundle.rest_pose.connect_ats[name]].local_position.array
              * result.scale_fit.segment_scales[parent]
        for name, parent in parents.items() if parent is not None
    }
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != previous["source_sha256"]:
            raise RuntimeError("Saved source changed during reconstruction comparison")
    return {
        "method": "Current numerical reconstruction from unchanged saved 3D keypoints; no inference, calibration, or Parquet publication",
        "packages": {name: json.loads(distribution(name).read_text("direct_url.json") or "{}")
                     for name in ("skellytracker", "skellyforge")},
        "before": previous,
        "after": {"frames": len(result.frames), "segments": len(parents),
                  "fitted_model_scale_mm": result.scale_fit.fitted_scale,
                  "edges": measure_hierarchy(parents, positions, rotations, fitted_offsets)},
    }


if __name__ == "__main__":
    main()
