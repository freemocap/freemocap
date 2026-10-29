"""Capture production definitions without calling processing handlers or reserving runs."""
from hashlib import sha256
import inspect
from pathlib import Path
from types import SimpleNamespace

STAGES = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')

def capture(recording_path: Path, calibration_path: Path) -> dict:
    from freemocap.core.pipeline.dataflow.recording_pipeline import build_recording_pipeline
    from freemocap.core.pipeline.dataflow.saved_spatial_pipeline import build_saved_spatial_pipeline
    from freemocap.core.pipeline.dataflow.application_pipeline import describe_active_operation
    from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
    from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
    from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
    from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
    from skellycam.core.recorders.videos.recording_info import RecordingInfo

    def forbidden_loader():
        raise RuntimeError('Definition preview must never execute a data loader')

    sources = RecordingVideoSources.resolve(recording_path)
    calibration = CalibrationResult.load_toml(calibration_path)
    recording = RecordingInfo(recording_name=recording_path.name, recording_directory=str(recording_path.parent))
    plans = []
    for first, start in enumerate(STAGES):
        for stop in STAGES[first:]:
            for annotate in (False, True):
                config = PosthocMocapPipelineConfig(start_stage=start, stop_stage=stop,
                    calibration_toml_path=str(calibration_path), board_mode='explicit', charuco_board=calibration.board,
                    export_to_blender=False, graph_annotate=annotate)
                session = RunSaveSession(source_run_id=0, target_run_id=0, expected_metadata=None)
                if first < 2:
                    graph, handlers = build_recording_pipeline(sources=sources, recording=recording,
                        config=config, run_session=session, execution_provider='cpu', annotate=annotate,
                        shutdown_flag=SimpleNamespace(value=False),
                        observation_loader=forbidden_loader if start == 'triangulation' else None)
                    builder = build_recording_pipeline
                else:
                    graph, handlers = build_saved_spatial_pipeline(config=config, source_loader=forbidden_loader,
                        run_session=session)
                    builder = build_saved_spatial_pipeline
                definition = graph.definition.model_dump(mode='json')
                assert set(handlers) == {node['operation'] for node in definition['nodes']}
                path = Path(inspect.getsourcefile(builder))
                plans.append(dict(id=f'{start}:{stop}:{int(annotate)}', start=start, stop=stop,
                    annotate=annotate, definition=definition,
                    labels={node.id: describe_active_operation(node.id) for node in graph.definition.nodes},
                    source_file=str(path), source_sha256=sha256(path.read_bytes()).hexdigest(),
                    config=config.model_dump(mode='json')))
    return dict(schema_version=1, mode='definition_only', recording=str(recording_path),
        calibration=str(calibration_path), cameras=[dict(id=c.camera_id, path=str(c.video_metadata.file_path),
            frames=c.video_metadata.frame_count) for c in sources.camera_sources], stages=STAGES, plans=plans,
        limitations=['No processing handlers were executed. No results or timings are simulated.',
            'Saved-stage variants describe topology; they do not assert that saved prerequisites exist.',
            'Board definition is taken explicitly from the selected calibration for this inspection.',
            'CPU configuration describes the plan; no inference session is opened. This is not the live application task.'])
