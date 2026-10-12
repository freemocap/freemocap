"""Run the experimental graph inside the application's existing managed task."""
from concurrent.futures import CancelledError
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from shutil import copy2
from threading import Lock
from uuid import uuid4

from freemocap.core.pipeline.dataflow.recording_pipeline import run_recording_pipeline
from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode

NODE_LABELS = {
    'load_and_track': 'Load videos and track poses',
    'match_and_triangulate': 'Match cameras and triangulate points',
    'filter_trajectories': 'Filter point trajectories',
    'align_reference': 'Align coordinates',
    'reconstruction_input': 'Prepare skeleton inputs',
    'fit_model_dimensions': 'Fit skeleton dimensions',
    'reconstruct_skeletons': 'Reconstruct skeletons',
    'observation_request': 'Prepare 2D results',
    'save_observations': 'Save 2D results',
    'spatial_request': 'Prepare 3D results',
    'save_spatial': 'Save 3D results',
    'save_recording': 'Save reconstructed recording',
}


def validate_application_graph(*, config: PosthocMocapPipelineConfig) -> None:
    if config.start_stage != 'observations':
        raise ValueError('Experimental graph currently starts at 2D tracking; choose the current pipeline to start from saved results')
    if config.charuco_tracking_enabled and config.board_mode != CharucoBoardMode.EXPLICIT:
        raise ValueError('Experimental graph requires an explicit ChArUco board; choose a board or disable board tracking')
    if not config.calibration_toml_path or not Path(config.calibration_toml_path).is_file():
        raise ValueError('Experimental graph requires an existing camera calibration file')
    if config.detector_type == 'mediapipe' and config.graph_execution_provider == 'cuda':
        raise ValueError('The installed MediaPipe adapter supports CPU only; choose automatic or CPU')


def run_application_graph(*, request) -> None:
    # Import here to preserve the pipeline's existing lifecycle without a module cycle.
    from freemocap.core.pipeline.posthoc.mocap_pipeline import complete_mocap
    from freemocap.core.recording.exports.requests import ScientificExportOptions
    validate_application_graph(config=request.config)
    request.report('setting_up', 'Preparing experimental graph', 0.0)
    sources = RecordingVideoSources.resolve(Path(request.recording.full_recording_path))
    if not request.ipc.should_continue:
        raise CancelledError('Experimental graph cancelled during setup')
    provider = request.config.graph_execution_provider
    if provider == 'auto':
        if request.config.detector_type == 'mediapipe':
            provider = 'cpu'
        else:
            import onnxruntime
            provider = 'cuda' if 'CUDAExecutionProvider' in onnxruntime.get_available_providers() else 'cpu'
    # Keep the graph's calibration updates local to this recording. Never rewrite
    # the user's selected calibration from another recording.
    calibration = Path(request.config.calibration_toml_path).resolve()
    destination = sources.recording_path / 'calibration_copies' / f'{sha256(calibration.read_bytes()).hexdigest()}-{uuid4().hex}.toml'
    destination.parent.mkdir(exist_ok=True)
    copy2(calibration, destination)
    config = request.config.model_copy(update={
        'calibration_toml_path': str(destination), 'export_to_blender': False,
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
            labels = [NODE_LABELS.get(name, 'Save annotated camera video' if name.startswith('annotate_camera_') else name)
                      for name in sorted(active)]
            if event == 'tracking':
                count = sources.camera_sources[0].video_metadata.frame_count
                request.report('collecting_camera_output',
                    f'Experimental graph ({provider}): tracking {fraction * count:.0f}/{count} motion-capture frames across {len(sources.camera_sources)} videos', fraction)
            else:
                request.report('reconstructing',
                    f'Experimental graph ({provider}): {len(finished)} operations finished; ' + ('; '.join(labels) or 'finishing'), 0.0)

    result = run_recording_pipeline(sources=sources, recording=request.recording, config=config,
        execution_provider=provider, annotate=request.config.graph_annotate,
        shutdown_flag=request.ipc.pipeline_shutdown_flag, performance=request.performance, progress=progress)
    if result.cancelled or not request.ipc.should_continue:
        raise CancelledError('Experimental graph cancelled; completed checkpoints may remain')
    if not result.complete:
        details = '; '.join(f'{node}: {error}' for node, error in result.failures.items())
        raise RuntimeError(f'Experimental graph incomplete: {details}; blocked operations: {", ".join(result.blocked)}')
    # The app owns optional exports and terminal reporting, exactly as for its
    # current pipeline. The graph above has not run these exports a second time.
    complete_mocap(replace(request, config=request.config.model_copy(update={'calibration_toml_path': str(destination)})))
