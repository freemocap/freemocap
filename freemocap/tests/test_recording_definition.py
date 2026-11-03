"""Pure topology must remain available without any runtime setup."""
from types import SimpleNamespace
import pytest
from freemocap.core.pipeline.dataflow.recording_definition import recording_definition, saved_spatial_definition

STAGES = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')

@pytest.mark.parametrize('start,stop', [(a,b) for i,a in enumerate(STAGES) for b in STAGES[i:]])
def test_pure_stage_recipes_are_closed_and_stable(start, stop):
    # A structural config proves recipe construction needs no model/calibration/run objects.
    config = SimpleNamespace(start_stage=start, stop_stage=stop,
        export_options=SimpleNamespace(formats=[]), export_tall_csv=False)
    build = (lambda: recording_definition(config=config, camera_count=3, annotate=True)) if start in STAGES[:2] else lambda: saved_spatial_definition(config=config)
    graph = build()
    assert graph == build()
    assert len(graph.topological_order) == len(graph.definition.nodes)
    positions = {name:i for i,name in enumerate(graph.topological_order)}
    for edge in graph.definition.edges:
        assert positions[edge.source.node] < positions[edge.target.node]
    nodes = set(positions)
    assert ('reconstruct_skeletons' in nodes) == (stop == 'reconstruction')
    if stop == 'observations':
        assert 'match_and_triangulate' not in nodes
    if start in STAGES[:2]:
        assert {f'annotate_camera_{i}' for i in range(3)} <= nodes
    if start == 'reconstruction':
        assert 'load_saved_model_fits' in nodes
        assert 'fit_model_dimensions' not in nodes


def test_recipe_does_not_retype_consumer_to_match_wrong_producer():
    from freemocap.core.pipeline.dataflow.recording_definition import _Recipe, RECORDING_INPUT_CONTRACTS
    recipe = _Recipe(RECORDING_INPUT_CONTRACTS)
    recipe.add('load_and_track', 'wrong_type', {})
    recipe.add('match_and_triangulate', 'raw_recording_geometry', {'observations':'load_and_track'})
    with pytest.raises(ValueError):
        recipe.compile()


def test_saved_observations_restart_is_a_read_only_node():
    config = SimpleNamespace(start_stage='triangulation',stop_stage='triangulation',
        export_options=SimpleNamespace(formats=[]),export_tall_csv=False)
    graph = recording_definition(config=config,camera_count=3)
    assert next(node for node in graph.definition.nodes if node.id == 'save_observations').effects == ('read_record',)
