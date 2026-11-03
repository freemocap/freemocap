"""Write the processing-plan fixtures used by the graph view's unit tests.

The graphs come from the production recipes in recording_definition.py, loaded without the
application package; read paths follow build_processing_plan for freemocap_sample_data.

Usage: python freemocap-ui/tools/make-processing-plan-fixtures.py <freemocap repo> <fixtures dir>
"""
import importlib.util
import json
import sys
import types
from pathlib import Path


def load(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main(repo: Path, out: Path) -> None:
    dataflow = repo / 'freemocap/core/pipeline/dataflow'
    for package in ('freemocap', 'freemocap.core', 'freemocap.core.pipeline', 'freemocap.core.pipeline.dataflow'):
        sys.modules[package] = types.ModuleType(package)
    definition = load('freemocap.core.pipeline.dataflow.definition', dataflow / 'definition.py')
    recipes = load('freemocap.core.pipeline.dataflow.recording_definition', dataflow / 'recording_definition.py')
    out.mkdir(parents=True, exist_ok=True)
    videos = [f'/recordings/freemocap_sample_data/synchronized_videos/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam{i}.mp4' for i in (1, 2, 3)]
    parquet = '/recordings/freemocap_sample_data/freemocap_sample_data_data.parquet'
    calibration = '/recordings/freemocap_sample_data/freemocap_sample_data_camera_calibration.toml'
    cases = {'full': ('observations', 'reconstruction'), 'from-filtering': ('filtering', 'reconstruction'),
             'to-triangulation': ('observations', 'triangulation')}
    for name, (start, stop) in cases.items():
        config = types.SimpleNamespace(start_stage=start, stop_stage=stop, export_tall_csv=False,
                                       export_options=types.SimpleNamespace(formats=[]))
        compiled = (recipes.recording_definition(config=config, camera_count=3, annotate=True)
                    if start in ('observations', 'triangulation') else recipes.saved_spatial_definition(config=config))
        graph = compiled.definition
        reads: dict[str, list[str]] = {}
        for node in graph.nodes:
            if node.id == 'load_and_track': reads[node.id] = videos
            elif node.id == 'match_and_triangulate': reads[node.id] = [calibration]
            elif node.id.startswith('annotate_camera_'): reads[node.id] = [videos[int(node.id.removeprefix('annotate_camera_'))]]
            elif 'read_record' in node.effects: reads[node.id] = [parquet]
        plan = {'plan_id': '', 'recording_path': '/recordings/freemocap_sample_data',
                'graph': graph.model_dump(mode='json'), 'topological_order': list(compiled.topological_order),
                'configuration': {}, 'read_paths': reads}
        plan['plan_id'] = f'fixture-{name}'
        (out / f'plan-{name}.json').write_text(json.dumps({'plan': plan, 'errors': []}, indent=1))
        print(name, len(graph.nodes), 'nodes')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python make-processing-plan-fixtures.py <freemocap repo> <fixtures dir>')
    main(repo=Path(sys.argv[1]), out=Path(sys.argv[2]))
