"""Old settings are accepted as inputs; schemas and writers use current names."""
import pytest
from pydantic import ValidationError

from freemocap.core.recording.exports.requests import ExportOptions
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


@pytest.mark.parametrize('key', ['scientific_exports', 'scientificExports', 'export_options', 'exportOptions'])
def test_saved_export_settings_load_and_write_canonical_names(key):
    options = {'formats': ['wide_csv', 'npz'], 'data': ['RAW_KEYPOINTS_3D']}
    config = PosthocMocapPipelineConfig.model_validate({key: options})
    assert config.export_options == ExportOptions.model_validate(options)
    written = config.model_dump(mode='json', by_alias=True)
    assert written['exportOptions']['formats'] == options['formats']
    assert not any('scientific' in name.lower() for name in written)
    schema = PosthocMocapPipelineConfig.model_json_schema()
    assert 'exportOptions' in schema['properties']
    assert not any('scientific' in name.lower() for name in schema['properties'])


def test_conflicting_aliases_fail_but_equivalent_options_are_accepted():
    with pytest.raises(ValidationError, match='Conflicting export options'):
        PosthocMocapPipelineConfig.model_validate({
            'scientificExports': {'formats': ['npy']}, 'exportOptions': {'formats': ['npz']},
        })
    config = PosthocMocapPipelineConfig.model_validate({
        'scientific_exports': {'formats': ['npy']},
        'exportOptions': ExportOptions(formats=('npy',)).model_dump(mode='json'),
    })
    assert config.export_options.formats == ('npy',)


def test_explicit_channel_override_survives_historical_setting_migration():
    selection = {'sensor_group': 'cameras', 'source': 'tracker', 'reference_frame': 'world',
                 'channel': 'RAW_KEYPOINTS_3D', 'static': False}
    config = PosthocMocapPipelineConfig.model_validate({'scientificExports': {
        'formats': ['wide_csv'], 'wide_csv': [selection],
    }})
    assert config.export_options.wide_csv[0].model_dump(mode='json') == selection
