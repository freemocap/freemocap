"""Execute requested numerical stages from saved arrays using the graph executor."""
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import replace
import numpy as np

from freemocap.core.pipeline.dataflow.definition import (
    DataContract, DataGranularity, GraphConnection, GraphDefinition, GraphNode,
    GraphPort, InputBindingRule, PortReference, compile_graph,
)
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
):
    if (source is None) == (source_loader is None):
        raise ValueError("Provide either validated saved inputs or a saved-input loader")
    nodes, edges, handlers = [], [], {}

    def operation(name, kind, dependencies, function, resource='compute'):
        def port(label, contract):
            return GraphPort(name=label, contract=DataContract(kind=contract, data_granularity=DataGranularity.RECORDING))
        nodes.append(GraphNode(id=name, operation=name, execution_resource=resource,
            inputs=tuple(port(label, contract) for label, (_, contract) in dependencies.items()),
            outputs=(port('result', kind),)))
        for label, (parent, _) in dependencies.items():
            edges.append(GraphConnection(source=PortReference(node=parent, port='result'),
                target=PortReference(node=name, port=label), binding=InputBindingRule.SAME_KEY))
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
            if progress:
                progress(name, 'finished', 1.0)
            return {'result': result}
        handlers[name] = invoke

    operation('load_saved_spatial', 'saved_spatial_inputs', {},
              lambda _: source_loader() if source_loader is not None else source, resource='recording_io')
    if config.start_stage == 'filtering':
        operation('filter_trajectories', 'filtered_trajectories', {'source': ('load_saved_spatial', 'saved_spatial_inputs')},
            lambda inputs: prepare_recording_points(points=inputs['source'].points.values,
                timestamps_s=np.asarray(inputs['source'].points.timestamps_s), config=config.filter_config))
    dependencies = {'source': ('load_saved_spatial', 'saved_spatial_inputs')}
    if config.start_stage == 'filtering':
        dependencies['filtered'] = ('filter_trajectories', 'filtered_trajectories')

    def reconstruction_input(inputs):
        saved = inputs['source']
        if 'filtered' not in inputs:
            return saved.numerical
        filtered = inputs['filtered']
        return replace(saved.numerical, keypoints_3d=filtered.points,
            measured_support=filtered.report.gap_filling.measured_support(filtered.points))
    operation('reconstruction_input', 'reconstruction_input', dependencies, reconstruction_input)
    save_inputs = {'source': ('load_saved_spatial', 'saved_spatial_inputs'),
                   'request': ('reconstruction_input', 'reconstruction_input')}
    if config.start_stage == 'filtering':
        save_inputs['filtered'] = ('filter_trajectories', 'filtered_trajectories')
    if config.stop_stage != 'filtering':
        fit_node = 'load_saved_model_fits' if config.start_stage == 'reconstruction' else 'fit_model_dimensions'
        operation(fit_node, 'recording_model_fits', {
            'source': ('load_saved_spatial', 'saved_spatial_inputs'),
            'request': ('reconstruction_input', 'reconstruction_input')},
            lambda inputs: load_saved_model_fits(inputs['source'], inputs['request']) if config.start_stage == 'reconstruction'
                           else fit_skeletons_for_recording(inputs['request']))
        save_inputs['fits'] = (fit_node, 'recording_model_fits')
        if config.stop_stage == 'reconstruction':
            operation('reconstruct_skeletons', 'reconstructed_models', {
                'request': ('reconstruction_input', 'reconstruction_input'), 'fits': (fit_node, 'recording_model_fits')},
                lambda inputs: reconstruct_skeletons_with_fits(request=inputs['request'], fits=inputs['fits']))
            save_inputs['results'] = ('reconstruct_skeletons', 'reconstructed_models')
    operation('save_stage_result', 'saved_recording', save_inputs, lambda inputs:
        save_numerical_checkpoint(source=inputs['source'], config=config, numerical=inputs['request'],
            filtering=inputs['filtered'].report if 'filtered' in inputs else inputs['source'].filtering,
            fits=inputs.get('fits', {}), results=inputs.get('results', {}), run_session=run_session, cancelled=cancelled), resource='recording_io')
    return compile_graph(GraphDefinition(nodes=tuple(nodes), edges=tuple(edges))), handlers
