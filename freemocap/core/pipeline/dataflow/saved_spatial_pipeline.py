"""Execute requested numerical stages from saved arrays using the graph executor."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import replace
import numpy as np

from freemocap.core.pipeline.dataflow.recording_definition import saved_spatial_definition
from freemocap.core.pipeline.dataflow.saved_spatial_source import SavedSpatialSource, load_saved_model_fits
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.reconstruction.posthoc_filtering import prepare_recording_points
from freemocap.core.reconstruction.posthoc_reconstruction import fit_skeletons_for_recording, reconstruct_skeletons_with_fits
from freemocap.core.recording.result_processing.numerical_checkpoint import save_numerical_checkpoint
from freemocap.core.recording.result_processing.run_save_session import RunSaveSession


def build_saved_spatial_pipeline(*, config: PosthocMocapPipelineConfig,
    source: SavedSpatialSource | None = None, source_loader: Callable[[], SavedSpatialSource] | None = None,
    run_session: RunSaveSession | None = None, cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[str, str, float], None] | None = None,
    artifacts: Callable | None = None,
):
    if (source is None) == (source_loader is None):
        raise ValueError("Provide either validated saved inputs or a saved-input loader")
    handlers = {}

    def operation(name, function):
        def invoke(inputs):
            if cancelled():
                raise CancelledError('Saved-stage processing cancelled')
            if progress:
                progress(name, 'started', 0.0)
            try:
                result = function(inputs)
            except Exception as error:
                if progress:
                    progress(name, 'cancelled' if isinstance(error, CancelledError) else 'failed', 0.0)
                raise
            if artifacts is not None:
                artifacts(name, result)
            if progress:
                progress(name, 'finished', 1.0)
            return {'result': result}
        handlers[name] = invoke

    operation('load_saved_spatial', lambda _: source_loader() if source_loader is not None else source)
    if config.start_stage == 'filtering':
        operation('filter_trajectories', lambda inputs: prepare_recording_points(points=inputs['source'].points.values,
                timestamps_s=np.asarray(inputs['source'].points.timestamps_s), config=config.filter_config))

    def reconstruction_input(inputs):
        saved = inputs['source']
        if 'filtered' not in inputs:
            return saved.numerical
        filtered = inputs['filtered']
        return replace(saved.numerical, keypoints_3d=filtered.points,
            measured_support=filtered.report.gap_filling.measured_support(filtered.points))
    operation('reconstruction_input', reconstruction_input)
    if config.stop_stage != 'filtering':
        fit_node = 'load_saved_model_fits' if config.start_stage == 'reconstruction' else 'fit_model_dimensions'
        operation(fit_node, lambda inputs: load_saved_model_fits(inputs['source'], inputs['request']) if config.start_stage == 'reconstruction'
                           else fit_skeletons_for_recording(inputs['request']))
        if config.stop_stage == 'reconstruction':
            operation('reconstruct_skeletons', lambda inputs: reconstruct_skeletons_with_fits(request=inputs['request'], fits=inputs['fits']))
    operation('save_stage_result', lambda inputs:
        save_numerical_checkpoint(source=inputs['source'], config=config, numerical=inputs['request'],
            filtering=inputs['filtered'].report if 'filtered' in inputs else inputs['source'].filtering,
            fits=inputs.get('fits', {}), results=inputs.get('results', {}), run_session=run_session, cancelled=cancelled))
    graph = saved_spatial_definition(config=config)
    return graph, {node.id: handlers[node.id] for node in graph.definition.nodes}
