"""Replay saved reference predictions through production temporal processing.

Run with ``python -m freemocap.tests.reference_recordings.temporal_comparison``.
No cameras, detectors, GUI, or source-recording writes are used. Readers acquire
the normal recording lock. Timings exclude decoding/inference and transport.
Recordings are comparison inputs, not independent motion ground truth.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import time
import tracemalloc

import numpy as np
from skellyforge.core.data_tensors.channel_values import ChannelValues, SPATIAL_COMPONENTS
from skellyforge.core.math.geometry.spatial_vectors import Point

from freemocap.core.pipeline.realtime.temporal_pipeline import TemporalPipeline
from freemocap.core.reconstruction.coordinate_conventions import CALIBRATION_TO_RECONSTRUCTION, RECONSTRUCTION_TO_CALIBRATION
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
from freemocap.core.skeletons.reconstruct_skeleton import reconstruct_skeleton
from freemocap.core.skeletons.reconstruction_state import build_reconstruction_states, streaming_model_scale_source
from freemocap.core.skeletons.standard_human_skeleton import build_standard_human_bundle
from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
from freemocap.core.tasks.calibration.shared.calibration_state import CalibrationStateTracker
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import OneEuroConfig, RealtimeFilterConfig
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.tests.reference_paths import prepared_root
from freemocap.tools.datasets.preparation import file_digest


@dataclass
class CameraPredictions:
    camera_id: str
    timestamps: np.ndarray
    coordinates: np.ndarray
    confidence: np.ndarray
    observation: object


@dataclass
class ReplayInputs:
    timestamps: np.ndarray
    cameras: tuple[CameraPredictions, ...]
    names: tuple[str, ...]
    calibration: CalibrationStateTracker
    detector_type: str
    confidence_threshold: float


def load_inputs(recording: Path) -> ReplayInputs:
    structure = RecordingStructure(base_directory=recording.parent, recording_name=recording.name)
    with recording_view(structure.data_parquet_path) as view:
        run_id = view.metadata.selected_run_id
    saved = read_saved_observations(structure=structure, run_id=run_id, sensor_group=None)
    cameras = []
    for camera_id, series in saved.frames.camera_series.items():
        observation = series.annotation_frame(0)
        observation.stages = {'body': observation.stages['body']}
        indices = np.asarray(series.stage_indices['body'])
        arrays = series.channel_arrays
        coordinates = arrays.values[:, indices][:, :, [arrays.components.index('x'), arrays.components.index('y')]]
        confidence = arrays.values[:, indices, arrays.components.index('visibility')]
        cameras.append(CameraPredictions(camera_id, np.asarray(saved.timing.cameras[camera_id].timestamps_s),
            coordinates, confidence, observation))
    names = cameras[0].observation.stages['body'].keypoints.names
    if any(camera.observation.stages['body'].keypoints.names != names for camera in cameras):
        raise ValueError('Comparison requires identical declared detector layouts across cameras')
    calibration = CalibrationStateTracker.create_and_try_load(find_recording_calibration(recording_folder=recording))
    binding = calibration.bind_live_cameras(live_camera_indices={camera.camera_id: i for i, camera in enumerate(cameras)})
    if not binding or not binding.applicable or binding.kind.value != 'exact':
        raise ValueError('Reference comparison requires exact calibration identities, not an inferred ordering')
    return ReplayInputs(np.asarray(saved.timing.synchronized.timestamps_s), tuple(cameras), names,
        calibration, saved.config.detector_type, float(saved.config.rtmpose_confidence_threshold))


def profile_config(profile: str, gap_s: float, image_beta: float = .03) -> RealtimeFilterConfig:
    return RealtimeFilterConfig(
        image_smoothing=OneEuroConfig(enabled=profile in ('image', 'combined'), beta=image_beta),
        spatial_smoothing=OneEuroConfig(enabled=profile in ('spatial', 'combined')),
        gap_duration_s=gap_s, segment_retention_s=gap_s,
    )


def disturbed_inputs(inputs: ReplayInputs) -> tuple[ReplayInputs, np.ndarray]:
    elapsed = inputs.timestamps - inputs.timestamps[0]
    hidden = np.zeros((len(elapsed), len(inputs.names)), dtype=bool)
    shoulders = np.asarray([name in ('left_shoulder', 'right_shoulder') for name in inputs.names])
    hidden |= ((elapsed >= 6.) & (elapsed < 6.25))[:, None] & shoulders
    hidden[(elapsed >= 18.) & (elapsed < 18.4)] = True
    hidden[(elapsed >= 28.) & (elapsed < 28.8)] = True
    rng = np.random.default_rng(712)
    cameras = []
    for camera in inputs.cameras:
        coordinates = camera.coordinates + rng.normal(0., 2., camera.coordinates.shape)
        coordinates[hidden] = np.nan
        cameras.append(replace(camera, coordinates=coordinates))
    return replace(inputs, cameras=tuple(cameras)), hidden


def replay(inputs: ReplayInputs, config: RealtimeFilterConfig, *, reconstruct: bool = True):
    temporal = TemporalPipeline(config)
    bundle = build_standard_human_bundle(detector_type=inputs.detector_type)
    state = build_reconstruction_states(bundles=(bundle,),
        scale_source_for=streaming_model_scale_source(window_frames=config.segment_scale_window_frames))[bundle.model_id]
    shape = (len(inputs.timestamps), len(inputs.names), len(SPATIAL_COMPONENTS))
    coordinates = np.full(shape, np.nan)
    status = np.zeros(shape[:-1], dtype=np.uint8)
    segment_present = np.zeros((len(inputs.timestamps), len(bundle.skeleton.segments)), dtype=bool)
    elapsed_ms = np.empty(len(inputs.timestamps))
    temporal_ms = np.empty(len(inputs.timestamps))
    source_start = inputs.timestamps[0]
    for frame, timestamp in enumerate(inputs.timestamps):
        start = time.perf_counter_ns()
        observations = {}
        for camera in inputs.cameras:
            observation = camera.observation
            observation.frame_number = frame
            points = observation.stages['body'].keypoints
            np.copyto(points.xy, camera.coordinates[frame])
            np.copyto(points.visibility, camera.confidence[frame])
            observations[camera.camera_id] = temporal.image_observation(camera_id=camera.camera_id,
                observation=observation, timestamp_s=float(camera.timestamps[frame] - source_start + 1.),
                confidence_threshold=inputs.confidence_threshold)
        image_end = time.perf_counter_ns()
        result = inputs.calibration.try_angulate(frame_number=frame, frame_observations_by_camera=observations,
            max_reprojection_error_px=config.max_reprojection_error_px)
        if result is None:
            raise RuntimeError('Reference triangulation failed')
        points = result.points
        converted = CALIBRATION_TO_RECONSTRUCTION.convert_point(
            point=Point.from_prevalidated_array(array=points.data_values)).array
        raw = ChannelValues(points.names, converted, points.entry_present, component_names=SPATIAL_COMPONENTS)
        spatial_start = time.perf_counter_ns()
        output = temporal.process(timestamp_s=float(timestamp - source_start + 1.), points=raw)
        spatial_end = time.perf_counter_ns()
        if reconstruct:
            skeleton = reconstruct_skeleton(bundle=bundle, state=state, filtered_keypoints=output.positions,
                observed_keypoints=output.observed_positions, timestamp_s=float(timestamp - source_start + 1.),
                segment_retention_s=config.segment_retention_s, compute_center_of_mass=False)
            if skeleton is not None:
                segment_present[frame] = np.isfinite(skeleton.segment_origins.aligned(tuple(bundle.skeleton.segments))).all(axis=-1)
        end = time.perf_counter_ns()
        coordinates[frame] = output.positions.aligned(inputs.names)
        status[frame] = np.nan_to_num(output.sample_status.aligned(inputs.names), nan=0).astype(np.uint8)
        elapsed_ms[frame] = (end - start) / 1e6
        temporal_ms[frame] = (image_end - start + spatial_end - spatial_start) / 1e6
    return coordinates, status, segment_present, elapsed_ms, temporal_ms


def finite_rms(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite * finite))) if finite.size else None


def comparisons(inputs: ReplayInputs, image_beta: float = .03, profiles: tuple[str, ...] = ('none', 'image', 'spatial', 'combined')):
    baseline = replay(inputs, profile_config('none', 0.))
    disturbed, hidden = disturbed_inputs(inputs)
    baseline_values, _, baseline_segments, _, _ = baseline
    target_present = np.isfinite(baseline_values).all(axis=-1)
    results = []
    for profile, gap_s in [('none', 0.)] + [(p, g) for p in profiles for g in (.1, .3, .5)]:
        config = profile_config(profile, gap_s, image_beta)
        values, statuses, segments, elapsed, temporal_cost = replay(disturbed, config)
        present = np.isfinite(values).all(axis=-1)
        comparable = present & target_present
        gap_comparable = comparable & hidden
        results.append({
            'profile': profile, 'gap_ms': gap_s * 1000, 'config': config.model_dump(mode='json'),
            'available_reference_cells': int(target_present.sum()),
            'missing_reference_points_percent': float(100 * np.mean(~present[target_present])),
            'missing_reference_segments_percent': float(100 * np.mean(~segments[baseline_segments])),
            'generated_percent': float(100 * np.mean(statuses > 1)),
            'recovery_available_percent': float(100 * np.mean(present[hidden & target_present])),
            'recovery_error_rmse_mm': finite_rms((values - baseline_values)[gap_comparable]),
            'perturbation_and_filter_deviation_rmse_mm': finite_rms((values - baseline_values)[comparable & ~hidden]),
            'total_p50_ms': float(np.median(elapsed[1:])), 'total_p95_ms': float(np.percentile(elapsed[1:], 95)),
            'temporal_p50_ms': float(np.median(temporal_cost[1:])), 'temporal_p95_ms': float(np.percentile(temporal_cost[1:], 95)),
        })
        print(json.dumps({k: v for k, v in results[-1].items() if k != 'config'}), flush=True)
    return baseline_values, results


def controlled_motion(inputs: ReplayInputs, reference: np.ndarray, image_beta: float = .03):
    valid = np.isfinite(reference).all(axis=-1)
    first_valid = np.argmax(valid, axis=0)
    stationary = reference[first_valid, np.arange(reference.shape[1])].copy()
    sample_times = np.arange(180, dtype=np.float64) / 30.
    truth = np.broadcast_to(stationary, (len(sample_times), *stationary.shape)).copy()
    truth[sample_times >= 2., :, SPATIAL_COMPONENTS.index('z')] += 100.
    calibration_points = RECONSTRUCTION_TO_CALIBRATION.convert_point(
        point=Point.from_prevalidated_array(array=truth.reshape(-1, len(SPATIAL_COMPONENTS)))).array
    projected = inputs.calibration.triangulator.project(calibration_points)
    projected = projected.reshape(len(inputs.cameras), len(sample_times), len(inputs.names), -1)
    rng = np.random.default_rng(1712)
    by_id = {camera.camera_id: camera for camera in inputs.cameras}
    cameras = []
    for index, camera_id in enumerate(inputs.calibration.triangulator.camera_ids):
        camera = by_id[camera_id]
        cameras.append(replace(camera, timestamps=sample_times,
            coordinates=projected[index] + rng.normal(0., 1., projected[index].shape),
            confidence=np.ones(projected[index].shape[:-1])))
    synthetic = replace(inputs, timestamps=sample_times, cameras=tuple(cameras))
    results = []
    for profile in ('none', 'image', 'spatial', 'combined'):
        values, _, _, _, costs = replay(synthetic, profile_config(profile, .3, image_beta), reconstruct=False)
        settled = (sample_times >= .5) & (sample_times < 1.8)
        displacement = np.nanmedian(values[:, :, SPATIAL_COMPONENTS.index('z')] - stationary[:, SPATIAL_COMPONENTS.index('z')], axis=1)
        reached = np.flatnonzero((sample_times >= 2.) & (displacement >= 90.))
        results.append({'profile': profile, 'image_beta': image_beta,
            'stationary_jitter_mm': finite_rms(values[settled] - np.nanmean(values[settled], axis=0)),
            'stationary_rmse_mm': finite_rms((values - truth)[settled]),
            'step_90_percent_delay_ms': float((sample_times[reached[0]] - 2.) * 1000) if reached.size else None,
            'temporal_p95_ms': float(np.percentile(costs[1:], 95))})
    return results


def allocation_probe(reference: np.ndarray, names: tuple[str, ...]):
    config = RealtimeFilterConfig()
    temporal = TemporalPipeline(config)
    point_values = reference[np.argmax(np.isfinite(reference).all(axis=-1).sum(axis=-1))]
    points = ChannelValues(names, point_values, component_names=SPATIAL_COMPONENTS)
    for index in range(10):
        temporal.process(timestamp_s=float(index / 30.), points=points)
    workspace_ids = tuple(id(getattr(temporal.spatial_filter, name)) for name in ('_positions', '_velocities', '_times', '_difference'))
    tracemalloc.start()
    tracemalloc.reset_peak()
    initial, _ = tracemalloc.get_traced_memory()
    for index in range(10, 40):
        temporal.process(timestamp_s=float(index / 30.), points=points)
    final, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert workspace_ids == tuple(id(getattr(temporal.spatial_filter, name)) for name in ('_positions', '_velocities', '_times', '_difference'))
    return {'spatial_30_frame_peak_kib': (peak - initial) / 1024,
            'spatial_30_frame_retained_kib': (final - initial) / 1024, 'workspace_reused': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('.test-artifacts/filter-audit/temporal-comparison.json'))
    parser.add_argument('--datasets', nargs='+', default=['freemocap_test_data', 'freemocap_sample_data'])
    parser.add_argument('--image-beta', nargs='+', type=float, default=[.03])
    parser.add_argument('--profiles', nargs='+', choices=['none', 'image', 'spatial', 'combined'], default=['none', 'image', 'spatial', 'combined'])
    parser.add_argument('--controlled-only', action='store_true')
    args = parser.parse_args()
    report = {'method': 'Saved detector predictions; 2 px seeded image noise; shoulder gap 250 ms at 6 s, complete gap 400 ms at 18 s, complete gap 800 ms at 28 s. Comparison error uses undisturbed unfiltered triangulation, not motion ground truth.',
              'controlled_method': 'Reference calibration projects known stationary positions and a 100 mm vertical step at 30 Hz; independent 1 px Gaussian image noise, seed 1712. No skeleton reconstruction in controlled filter timings.',
              'datasets': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for dataset in args.datasets:
        recording = Path(json.loads((prepared_root() / dataset / 'ready.json').read_text())['recording'])
        source_files = [recording / f'{recording.name}_data.parquet', find_recording_calibration(recording_folder=recording)]
        source_hashes = {str(path): file_digest(path) for path in source_files if path and path.exists()}
        inputs = load_inputs(recording)
        print(f'BEGIN {dataset}: {len(inputs.timestamps)} frames', flush=True)
        baseline, results = ((replay(inputs, profile_config('none', 0.), reconstruct=False)[0], [])
            if args.controlled_only else comparisons(inputs, args.image_beta[0], tuple(args.profiles)))
        report['datasets'][dataset] = {'frames': len(inputs.timestamps),
            'nominal_replay_fps': float(1. / np.median(np.diff(inputs.timestamps))),
            'comparisons': results, 'controlled': [result for beta in args.image_beta for result in controlled_motion(inputs, baseline, beta)],
            'allocation_probe': allocation_probe(baseline, inputs.names), 'source_hashes': source_hashes}
        assert source_hashes == {path: file_digest(Path(path)) for path in source_hashes}
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(f'REPORT {args.output}', flush=True)


if __name__ == '__main__':
    main()
