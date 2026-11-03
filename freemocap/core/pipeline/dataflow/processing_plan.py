"""Read-only application planning; no workers, models, output allocation or writes."""
from hashlib import sha256
import json
from pathlib import Path

from pydantic import Field, JsonValue

from freemocap.core.pipeline.dataflow.definition import (
    GraphDefinitionModel, GraphDefinition, GraphNode, GraphPort, DataContract,
    DataGranularity, GraphConnection, PortReference, InputBindingRule, compile_graph,
)
from freemocap.core.pipeline.dataflow.recording_definition import recording_definition, saved_spatial_definition
from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure, select_group, inspect_saved_stages
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


class ProcessingPlan(GraphDefinitionModel):
    plan_id: str
    recording_path: str
    graph: GraphDefinition
    topological_order: tuple[str, ...]
    configuration: dict[str, JsonValue]
    read_paths: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class PlanPreview(GraphDefinitionModel):
    plan: ProcessingPlan | None = None
    errors: tuple[str, ...] = ()


def plan_from_graph(*, graph, config, recording_path: Path, read_paths=None) -> ProcessingPlan:
    compiled = compile_graph(graph)
    payload = dict(recording_path=str(recording_path.resolve()), graph=graph.model_dump(mode='json'),
        topological_order=compiled.topological_order, configuration=config.model_dump(mode='json'),
        read_paths=read_paths or {})
    identity = sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return ProcessingPlan(plan_id=identity, **payload)


def application_definition(*, config, camera_count: int):
    # Runtime delegates final exports to its existing bounded export supervisor.
    numerical = config.model_copy(update={'export_to_blender': False,
        'export_options': config.export_options.model_copy(update={'formats': []}), 'export_tall_csv': False})
    graph = (recording_definition(config=numerical, camera_count=camera_count, annotate=config.graph_annotate)
        if config.start_stage in ('observations', 'triangulation') else saved_spatial_definition(config=numerical)).definition
    if config.stop_stage != 'reconstruction':
        return graph
    nodes, edges = list(graph.nodes), list(graph.edges)
    contract = DataContract(kind='saved_recording', data_granularity=DataGranularity.RECORDING)
    exports = []
    if config.export_options.formats: exports.append('channel_exports')
    if config.export_tall_csv: exports.append('tall_csv')
    if config.export_to_blender: exports.append('blender')
    # The app waits for the numerical graph (including annotations) before exports.
    for name in exports:
        parents = [node.id for node in graph.nodes if not any(edge.source.node == node.id for edge in graph.edges)]
        inputs = []
        for parent in parents:
            source = next(node for node in nodes if node.id == parent).outputs[0]
            inputs.append(GraphPort(name=parent, contract=source.contract))
            edges.append(GraphConnection(source=PortReference(node=parent, port=source.name),
                target=PortReference(node=name, port=parent), binding=InputBindingRule.SAME_KEY))
        effects = ('read_record', 'write_disk', 'display') if name == 'blender' and config.auto_open_blend_file else ('read_record', 'write_disk')
        nodes.append(GraphNode(id=name, operation=name, execution_resource='blender_export' if name == 'blender' else 'recording_export_manifest', stage='reconstruction',
            effects=effects, inputs=tuple(inputs), outputs=(GraphPort(name='result', contract=contract),)))
    return GraphDefinition(nodes=tuple(nodes), edges=tuple(edges))


def build_processing_plan(*, recording_path: Path, config: PosthocMocapPipelineConfig) -> ProcessingPlan:
    structure = recording_structure(str(recording_path))
    if not structure.full_path.is_dir(): raise ValueError('Recording directory does not exist')
    from freemocap.core.pipeline.dataflow.application_pipeline import validate_application_graph
    from freemocap.core.recording.result_processing.run_save_session import RunSaveSession
    validate_application_graph(config=config)
    RunSaveSession.inspect_source(structure=structure, source_run_id=config.base_run_id)
    reads = {}
    parquet = str(structure.data_parquet_path)
    if config.start_stage == 'observations':
        from freemocap.core.pipeline.dataflow.video_sources import RecordingVideoSources
        sources = RecordingVideoSources.resolve(structure.full_path)
        video_paths = tuple(str(source.video_metadata.file_path) for source in sources.camera_sources)
        camera_count = len(video_paths)
        reads['load_and_track'] = video_paths
        if config.sensor_group is not None and config.sensor_group != sources.sensor_group:
            raise ValueError('Configured sensor group differs from recording sources')
    else:
        meta = read_metadata(path=structure.data_parquet_path)
        if config.base_run_id not in meta.runs: raise ValueError('Requested saved run does not exist')
        run = meta.runs[config.base_run_id]
        group = select_group(run, config.sensor_group)
        inventory = inspect_saved_stages(str(structure.full_path))
        entry = next(g for r in inventory['runs'] if r['run_id'] == config.base_run_id for g in r['groups'] if g['sensor_group'] == group)
        prerequisite = {'triangulation':'observations', 'filtering':'triangulation', 'scale_fit':'filtering', 'reconstruction':'scale_fit'}[config.start_stage]
        if not entry['stages'][prerequisite]: raise ValueError(f'Missing saved {prerequisite} inputs')
        # Camera identities come from the selected saved observation channel.
        channels = [c for c in run.channels if c.sensor_group == group and str(c.kind) == 'OVERLAY_2D']
        cameras = tuple(run.reference_frames[c.reference_frame]['camera_id'] for c in channels)
        def video_path(camera):
            filename = run.sources[f'camera:{camera}'].definition['video_filename']
            canonical = structure.videos_synchronized_dir / filename
            flat = structure.full_path / 'synchronized_videos' / filename
            return str(canonical if canonical.is_file() or not flat.is_file() else flat)
        video_paths = tuple(video_path(camera) for camera in cameras)
        camera_count = len(cameras)
        reads['load_saved_observations' if config.start_stage == 'triangulation' else 'load_saved_spatial'] = (parquet,)
    if config.start_stage in ('observations','triangulation') and config.stop_stage != 'observations' and camera_count < 2:
        raise ValueError('Reconstruction requires at least two cameras')
    graph = application_definition(config=config, camera_count=camera_count)
    for node in graph.nodes:
        if node.id == 'match_and_triangulate': reads[node.id] = (config.calibration_toml_path,)
        elif node.id in ('save_observations','save_spatial','save_recording','save_stage_result','save_model_fits','load_saved_model_fits','channel_exports','tall_csv','blender'):
            reads[node.id] = (parquet,) if structure.data_parquet_path.exists() or node.id not in ('save_observations',) else ()
        elif node.id.startswith('annotate_camera_'):
            reads[node.id] = (video_paths[int(node.id.removeprefix('annotate_camera_'))],)
    return plan_from_graph(graph=graph, config=config, recording_path=structure.full_path, read_paths=reads)


def preview_processing_plan(*, recording_path: Path, config: PosthocMocapPipelineConfig) -> PlanPreview:
    try:
        return PlanPreview(plan=build_processing_plan(recording_path=recording_path, config=config))
    except (ValueError, FileNotFoundError, KeyError) as error:
        return PlanPreview(errors=(str(error),))
