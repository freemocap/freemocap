"""Pure application graph recipes shared by inspection and execution.

These declarations coordinate component interfaces; they never construct workers,
load numerical inputs or models, or reserve a destination run.
"""
from freemocap.core.pipeline.dataflow.definition import (
    CompiledGraph, DataContract, DataGranularity, GraphConnection, GraphDefinition,
    GraphNode, GraphPort, InputBindingRule, PortReference, compile_graph,
)


# Explicit producer declarations: clients must not infer these from node names.
NODE_SEMANTICS = {
    'load_and_track': ('observations', ('read_record',)),
    'load_saved_observations': ('observations', ('read_record',)),
    'load_saved_spatial': ('triangulation', ('read_record',)),
    'match_and_triangulate': ('triangulation', ('read_record',)),
    'filter_trajectories': ('filtering', ()),
    'align_reference': ('triangulation', ()),
    'reconstruction_input': ('scale_fit', ()),
    'fit_model_dimensions': ('scale_fit', ()),
    'load_saved_model_fits': ('scale_fit', ('read_record',)),
    'reconstruct_skeletons': ('reconstruction', ()),
    'observation_request': ('observations', ()),
    'save_observations': ('observations', ('read_record', 'write_disk')),
    'spatial_request': ('triangulation', ()),
    'save_spatial': ('filtering', ('read_record', 'write_disk')),
    'save_recording': ('reconstruction', ('read_record', 'write_disk')),
    'stage_result_request': ('triangulation', ()),
    'save_stage_result': ('filtering', ('read_record', 'write_disk')),
    'save_model_fits': ('scale_fit', ('read_record', 'write_disk')),
    'export_recording': ('reconstruction', ('read_record', 'write_disk')),
    'export_tall_csv': ('reconstruction', ('read_record', 'write_disk')),
}


RECORDING_INPUT_CONTRACTS = {
    "load_and_track": {},
    "load_saved_observations": {},
    "observation_request": {"observations": "camera_observations"},
    "save_observations": {"request": "observation_recording_request"},
    "match_and_triangulate": {"observations": "camera_observations"},
    "filter_trajectories": {"science": "raw_recording_geometry"},
    "align_reference": {"science": "raw_recording_geometry", "filtered": "filtered_trajectories"},
    "reconstruction_input": {"aligned": "aligned_recording", "filtered": "filtered_trajectories"},
    "fit_model_dimensions": {"request": "reconstruction_input"},
    "reconstruct_skeletons": {"request": "reconstruction_input", "fits": "recording_model_fits"},
    "spatial_request": {"request": "observation_recording_request", "science": "raw_recording_geometry",
                        "filtered": "filtered_trajectories", "aligned": "aligned_recording"},
    "save_spatial": {"request": "spatial_recording_request", "saved_observations": "saved_observations"},
    "save_recording": {"request": "spatial_recording_request", "aligned": "aligned_recording",
                       "reconstructions": "reconstructed_models", "saved_spatial": "saved_spatial"},
    "export_recording": {"saved": "saved_recording"},
    "export_tall_csv": {"saved": "saved_recording"},
    "annotate_camera": {"observations": "camera_observations"},
    "stage_result_request": {"request": "spatial_recording_request"},
    "filtered_request": {"request": "spatial_recording_request", "filtered": "filtered_trajectories"},
    "save_stage_result": {"request": "spatial_recording_request", "saved_observations": "saved_observations"},
    "save_model_fits": {"saved": "saved_spatial", "fits": "recording_model_fits"},
}

SAVED_INPUT_CONTRACTS = {
    'load_saved_spatial': {},
    'filter_trajectories': {'source': 'saved_spatial_inputs'},
    'reconstruction_input': {'source': 'saved_spatial_inputs', 'filtered': 'filtered_trajectories'},
    'fit_model_dimensions': {'source': 'saved_spatial_inputs', 'request': 'reconstruction_input'},
    'load_saved_model_fits': {'source': 'saved_spatial_inputs', 'request': 'reconstruction_input'},
    'reconstruct_skeletons': {'request': 'reconstruction_input', 'fits': 'recording_model_fits'},
    'save_stage_result': {'source': 'saved_spatial_inputs', 'request': 'reconstruction_input',
                         'filtered': 'filtered_trajectories', 'fits': 'recording_model_fits', 'results': 'reconstructed_models'},
}


class _Recipe:
    def __init__(self, input_contracts):
        self.nodes = []
        self.edges = []
        self.input_contracts = input_contracts

    def add(self, name, kind, dependencies, resource='compute', *, semantics=None):
        def port(label, contract):
            return GraphPort(name=label, contract=DataContract(kind=contract,
                data_granularity=DataGranularity.RECORDING))
        stage, effects = semantics if semantics is not None else NODE_SEMANTICS[name]
        required = self.input_contracts['annotate_camera' if name.startswith('annotate_camera_') else name]
        if self.input_contracts is RECORDING_INPUT_CONTRACTS and set(required) != set(dependencies):
            raise ValueError(f'Operation input bindings differ from its contract: {name}')
        self.nodes.append(GraphNode(stage=stage, effects=effects, id=name, operation=name, execution_resource=resource,
            inputs=tuple(port(label, required[label]) for label, parent in dependencies.items()),
            outputs=(port('result', kind),)))
        self.edges.extend(GraphConnection(source=PortReference(node=parent, port='result'),
            target=PortReference(node=name, port=label), binding=InputBindingRule.SAME_KEY)
            for label, parent in dependencies.items())

    def compile(self, sinks=None) -> CompiledGraph:
        nodes, edges = self.nodes, self.edges
        if sinks is not None:
            selected = set(sinks)
            pending = list(selected)
            while pending:
                target = pending.pop()
                for edge in edges:
                    if edge.target.node == target and edge.source.node not in selected:
                        selected.add(edge.source.node)
                        pending.append(edge.source.node)
            nodes = [node for node in nodes if node.id in selected]
            edges = [edge for edge in edges if edge.target.node in selected]
        return compile_graph(GraphDefinition(nodes=tuple(nodes), edges=tuple(edges)))


def recording_definition(*, config, camera_count: int, annotate: bool = False) -> CompiledGraph:
    if config.start_stage not in ('observations', 'triangulation'):
        raise ValueError('Video/observation graph requires observations or triangulation start')
    if camera_count < 1:
        raise ValueError('Recording graph requires at least one camera')
    r = _Recipe(RECORDING_INPUT_CONTRACTS)
    observation = 'load_and_track' if config.start_stage == 'observations' else 'load_saved_observations'
    r.add(observation, 'camera_observations', {})
    r.add('match_and_triangulate', 'raw_recording_geometry', {'observations': observation})
    r.add('filter_trajectories', 'filtered_trajectories', {'science': 'match_and_triangulate'})
    r.add('align_reference', 'aligned_recording', {'science': 'match_and_triangulate', 'filtered': 'filter_trajectories'})
    r.add('reconstruction_input', 'reconstruction_input', {'aligned': 'align_reference', 'filtered': 'filter_trajectories'})
    r.add('fit_model_dimensions', 'recording_model_fits', {'request': 'reconstruction_input'})
    r.add('reconstruct_skeletons', 'reconstructed_models', {'request': 'reconstruction_input', 'fits': 'fit_model_dimensions'})
    r.add('observation_request', 'observation_recording_request', {'observations': observation})
    r.add('save_observations', 'saved_observations', {'request': 'observation_request'}, 'recording_io',
        semantics=('observations', ('read_record',) if config.start_stage == 'triangulation' else ('read_record', 'write_disk')))
    r.add('spatial_request', 'spatial_recording_request', {'request': 'observation_request',
        'science': 'match_and_triangulate', 'filtered': 'filter_trajectories', 'aligned': 'align_reference'})
    r.add('save_spatial', 'saved_spatial', {'request': 'spatial_request', 'saved_observations': 'save_observations'}, 'recording_io')
    r.add('save_recording', 'saved_recording', {'request': 'spatial_request', 'saved_spatial': 'save_spatial',
        'aligned': 'align_reference', 'reconstructions': 'reconstruct_skeletons'}, 'recording_io')
    if config.export_options.formats:
        r.add('export_recording', 'export_manifest', {'saved': 'save_recording'})
    if config.export_tall_csv:
        r.add('export_tall_csv', 'tall_csv_manifest', {'saved': 'save_recording'})
    annotations = []
    if annotate:
        for index in range(camera_count):
            name = f'annotate_camera_{index}'
            r.add(name, 'annotated_video', {'observations': observation}, 'annotation',
                semantics=('observations', ('read_record', 'write_disk')))
            annotations.append(name)
    if config.stop_stage == 'reconstruction':
        return r.compile()
    if config.stop_stage == 'observations':
        terminal = 'save_observations'
    elif config.stop_stage == 'scale_fit':
        r.add('save_model_fits', 'saved_recording', {'saved': 'save_spatial', 'fits': 'fit_model_dimensions'}, 'recording_io')
        terminal = 'save_model_fits'
    else:
        r.add('stage_result_request', 'spatial_recording_request', {'request': 'spatial_request'})
        r.add('save_stage_result', 'saved_recording', {'request': 'stage_result_request',
            'saved_observations': 'save_observations'}, 'recording_io')
        terminal = 'save_stage_result'
    graph = r.compile([terminal, *annotations])
    return graph.model_copy(update={'definition': graph.definition.model_copy(update={'nodes': tuple(
        node.model_copy(update={'stage': config.stop_stage}) if node.id in ('stage_result_request', 'save_stage_result') else node
        for node in graph.definition.nodes)})})


def saved_spatial_definition(*, config) -> CompiledGraph:
    if config.start_stage not in ('filtering', 'scale_fit', 'reconstruction'):
        raise ValueError('Saved spatial graph requires filtering, scale_fit or reconstruction start')
    r = _Recipe(SAVED_INPUT_CONTRACTS)
    r.add('load_saved_spatial', 'saved_spatial_inputs', {}, 'recording_io')
    dependencies = {'source': 'load_saved_spatial'}
    if config.start_stage == 'filtering':
        r.add('filter_trajectories', 'filtered_trajectories', dependencies)
        dependencies = {**dependencies, 'filtered': 'filter_trajectories'}
    r.add('reconstruction_input', 'reconstruction_input', dependencies)
    save = {**dependencies, 'request': 'reconstruction_input'}
    if config.stop_stage != 'filtering':
        fit = 'load_saved_model_fits' if config.start_stage == 'reconstruction' else 'fit_model_dimensions'
        r.add(fit, 'recording_model_fits', {'source': 'load_saved_spatial', 'request': 'reconstruction_input'})
        save['fits'] = fit
        if config.stop_stage == 'reconstruction':
            r.add('reconstruct_skeletons', 'reconstructed_models', {'request': 'reconstruction_input', 'fits': fit})
            save['results'] = 'reconstruct_skeletons'
    r.add('save_stage_result', 'saved_recording', save, 'recording_io',
        semantics=(config.stop_stage, ('read_record', 'write_disk')))
    return r.compile()
