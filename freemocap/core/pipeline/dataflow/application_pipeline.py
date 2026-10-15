"""Run typed data flow graph V1 inside the application's existing managed task."""
from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
from threading import Lock

from freemocap.core.pipeline.dataflow.recording_pipeline import run_recording_pipeline
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig

NODE_LABELS = {
    'load_saved_spatial': 'Loading saved 3D points and their coordinate frame',
    'load_saved_model_fits': 'Loading saved skeleton body dimensions',
    'save_model_fits': 'Saving fitted skeleton body dimensions',
    'load_saved_observations': 'Loading saved 2D tracking and recording timing',
    'stage_result_request': 'Preparing completed 3D results in the requested coordinate frame',
    'save_stage_result': 'Saving the requested processing stages',
    'load_and_track': 'Reading videos and detecting poses and requested board points',
    'match_and_triangulate': 'Matching camera views and calculating 3D points',
    'filter_trajectories': 'Filling gaps and smoothing 3D point movements',
    'align_reference': 'Orienting 3D motion in the recording coordinate system',
    'reconstruction_input': 'Preparing 3D points for skeleton fitting',
    'fit_model_dimensions': 'Fitting skeleton body dimensions to this recording',
    'reconstruct_skeletons': 'Calculating skeleton positions and joint rotations',
    'observation_request': 'Preparing detected image points for saving',
    'save_observations': 'Saving detected image points to disk',
    'spatial_request': 'Preparing reconstructed 3D points for saving',
    'save_spatial': 'Saving reconstructed 3D points to disk',
    'save_recording': 'Saving reconstructed motion to the recording Parquet file',
}


def describe_active_operation(name: str) -> str:
    if name.startswith('annotate_camera_'):
        camera_number = int(name.removeprefix('annotate_camera_')) + 1
        return f'Drawing tracking overlays and saving annotated video {camera_number}'
    return NODE_LABELS.get(name, 'Processing recording data')



def validate_application_graph(*, config: PosthocMocapPipelineConfig) -> None:
    if config.start_stage in ('observations', 'triangulation') and config.stop_stage != 'observations' and (not config.calibration_toml_path or not Path(config.calibration_toml_path).is_file()):
        raise ValueError('Typed data flow graph V1 requires an existing camera calibration file')
    if config.start_stage == 'observations' and config.detector_type == 'mediapipe' and config.graph_execution_provider == 'cuda':
        raise ValueError('The installed MediaPipe adapter supports CPU only; choose automatic or CPU')


def run_application_graph(*, request) -> None:
    # Prevent simultaneous app attempts from allocating the same run/file paths.
    # This admission lock does not serialize nodes within the graph.
    from filelock import FileLock
    with FileLock(Path(request.recording.full_recording_path) / '.processing-run.lock', timeout=0):
        _run_application_graph(request=request)


def _run_application_graph(*, request) -> None:
    # Import here to preserve the pipeline's existing lifecycle without a module cycle.
    from freemocap.core.pipeline.posthoc.mocap_pipeline import complete_mocap
    from freemocap.core.recording.exports.requests import ScientificExportOptions
    validate_application_graph(config=request.config)
    from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
    from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure
    session = RunSaveSession.resolve(structure=recording_structure(str(request.recording.full_recording_path)),
        source_run_id=request.config.base_run_id, mode=request.config.run_save_mode)
    request.report('setting_up', 'Checking the inputs required for the selected processing stages', 0.0)
    saved_collection = None
    saved_spatial_loader = None
    sources = None
    resolved_config = request.config
    if request.config.start_stage in ('filtering', 'scale_fit', 'reconstruction'):
        from freemocap.core.pipeline.dataflow.saved_spatial_source import load_saved_spatial_source
        saved_spatial_loader = lambda: load_saved_spatial_source(path=Path(request.recording.full_recording_path), config=request.config)
    elif request.config.start_stage == 'triangulation':
        from freemocap.core.pipeline.dataflow.saved_observation_source import load_saved_observation_source
        sources, saved_collection, resolved_config = load_saved_observation_source(
            path=str(request.recording.full_recording_path), config=request.config)
    else:
        sources = RecordingVideoSources.resolve(Path(request.recording.full_recording_path))
    if not request.ipc.should_continue:
        raise CancelledError('Typed data flow graph V1 cancelled during setup')
    from freemocap.core.tracking.recording_board_selection import resolve_recording_board
    if saved_collection is None and saved_spatial_loader is None:
        resolved_config = resolve_recording_board(sources=sources, config=request.config,
            cancelled=lambda: not request.ipc.should_continue,
            report=lambda detail: request.report('setting_up', detail, 0.0))
    provider = request.config.graph_execution_provider
    if provider == 'auto' and request.config.start_stage == 'observations':
        if request.config.detector_type == 'mediapipe':
            provider = 'cpu'
        else:
            import onnxruntime
            provider = 'cuda' if 'CUDAExecutionProvider' in onnxruntime.get_available_providers() else 'cpu'
    # Processing reads the selected calibration without modifying it. Changed
    # geometry is exported only when the final scientific result is saved.
    config = resolved_config.model_copy(update={
        'export_to_blender': False,
        'scientific_exports': ScientificExportOptions(), 'export_tall_csv': False,
    })
    lock = Lock()
    active: set[str] = set()
    finished: set[str] = set()

    def progress(node: str, event: str, fraction: float) -> None:
        if not request.ipc.should_continue:
            request.ipc.pipeline_shutdown_flag.value = True
            return
        with lock:
            if event == 'started':
                active.add(node)
            elif event == 'finished':
                active.discard(node)
                finished.add(node)
            elif event in ('failed', 'cancelled'):
                active.discard(node)
            labels = [describe_active_operation(name) for name in sorted(active)]
            if event == 'tracking':
                count = sources.camera_sources[0].video_metadata.frame_count
                cameras = len(sources.camera_sources)
                total_images = count * cameras
                detector = 'RTMPose' if config.detector_type == 'rtmpose' else 'MediaPipe'
                device = 'CUDA GPU' if provider == 'cuda' else 'CPU'
                board_text = ' and ChArUco board points' if config.charuco_tracking_enabled else ''
                request.report_operation(node,
                    f'Detect poses{board_text} in {cameras} videos ({detector}, {device})',
                    'running', completed=round(fraction * total_images), total=total_images,
                    unit='camera images', phase='collecting_camera_output')
                request.report('collecting_camera_output',
                    f'Reading {cameras} videos and detecting poses{board_text} with {detector} on {device}. '
                    f'Processed {round(fraction * total_images):,} of {total_images:,} camera images '
                    f'({cameras} videos x {count:,} frames each). '
                    'This percentage is for detection only; 3D reconstruction and saving follow.', fraction)
            else:
                request.report_operation(node, describe_active_operation(node),
                    {'started': 'running', 'finished': 'complete', 'failed': 'failed',
                     'cancelled': 'cancelled'}[event])
                detail = '. Also running: '.join(labels) if labels else (
                    'The current processing steps have finished; checking remaining work and requested exports')
                request.report('reconstructing', detail + '. The recording is still processing.', 0.0)

    if saved_spatial_loader is not None:
        from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
        from freemocap.core.pipeline.dataflow.recording_executor import execute_recording_graph
        graph, handlers = build_saved_spatial_pipeline(source_loader=saved_spatial_loader, config=config, run_session=session,
            cancelled=lambda: not request.ipc.should_continue, progress=progress)
        result = execute_recording_graph(graph=graph, handlers=handlers,
            cancelled=lambda: not request.ipc.should_continue)
    else:
        source_options = {'observation_loader': lambda: saved_collection} if saved_collection is not None else {}
        result = run_recording_pipeline(sources=sources, recording=request.recording, config=config, run_session=session, **source_options,
            execution_provider=provider, annotate=request.config.graph_annotate,
            shutdown_flag=request.ipc.pipeline_shutdown_flag, performance=request.performance, progress=progress)
    for node, seconds in result.elapsed_seconds.items():
        request.performance.record(f'graph.{node}', seconds)
    for node, prerequisites in result.blocked.items():
        request.report_operation(node, describe_active_operation(node),
            'cancelled' if result.cancelled else 'failed',
            'Stopped before starting' if result.cancelled else
            'Cannot run because required work failed: ' + ', '.join(describe_active_operation(name) for name in prerequisites))
    if result.cancelled or not request.ipc.should_continue:
        raise CancelledError('Typed data flow graph V1 cancelled; completed checkpoints may remain')
    if not result.complete:
        details = '; '.join(f'{node}: {error}' for node, error in result.failures.items())
        raise RuntimeError(f'Typed data flow graph V1 incomplete: {details}; blocked operations: {", ".join(result.blocked)}')
    # The app owns optional exports and terminal reporting, exactly as for its
    # current pipeline. The graph above has not run these exports a second time.
    if config.stop_stage != 'reconstruction':
        from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase
        request.report(AggregatorPhase.COMPLETE,
            f'Requested stages saved through {config.stop_stage}. Later processing and final exports were not requested.', 1.0)
    else:
        complete_mocap(replace(request, config=resolved_config.model_copy(update={'base_run_id': session.target_run_id})))
