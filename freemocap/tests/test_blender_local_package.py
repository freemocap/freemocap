"""Core must route Blender targets to the installed add-on's host builder."""
import json
from unittest.mock import Mock

import pytest

from freemocap.core.blender import local_package


@pytest.fixture
def builder_source(tmp_path, monkeypatch):
    source = tmp_path / 'addon'
    tools = source / '_host_tools'
    tools.mkdir(parents=True)
    (tools / 'build_addon.py').write_text('''
import json
PLATFORMS = {'windows-x64': (), 'macos-arm64': (), 'macos-x64': (), 'linux-x64': ()}
def wheel_set(cache, python, platform, download):
    return []
def build(**options):
    path = options['output'] / 'built.zip'
    path.write_text(json.dumps({key: options[key] for key in ('kind', 'python', 'platform', 'blender_min', 'blender_max')}))
    return path
''')
    monkeypatch.setattr(local_package, 'addon_source', lambda: source)
    monkeypatch.setattr(local_package, 'expected_build', lambda: {'source_sha256': 'source'})
    monkeypatch.setattr(local_package, 'source_hash', lambda path: 'source')
    monkeypatch.setattr(local_package, 'storage_root', lambda: tmp_path / 'cache')
    validator = Mock()
    monkeypatch.setattr(local_package, 'validate_archive', validator)
    return source, validator


@pytest.mark.parametrize(('system', 'machine', 'target'), [
    ('Darwin', 'arm64', 'macos-arm64'), ('Darwin', 'aarch64', 'macos-arm64'),
    ('Darwin', 'x86_64', 'macos-x64'), ('Windows', 'AMD64', 'windows-x64'),
    ('Linux', 'x86_64', 'linux-x64'),
])
def test_automatic_packaging_uses_builder_platforms_and_validates_cached_archive(builder_source, system, machine, target):
    runtime = dict(blender=[5, 2, 1], python='3.13', system=system, machine=machine)
    archive, kind, checksum = local_package.build_from_dependency(runtime, 'source')
    assert json.loads(archive.read_text()) == dict(kind='extension', python='3.13', platform=target,
                                                 blender_min='5.2.0', blender_max='5.3.0')
    assert kind == 'extension'
    assert local_package.build_from_dependency(runtime, 'source') == (archive, kind, checksum)
    assert builder_source[1].call_count == 2


@pytest.mark.parametrize(('version', 'python', 'system', 'machine'), [
    ([5, 2, 1], '3.13', 'Linux', 'arm64'),
])
def test_missing_builder_platform_fails_before_packaging(builder_source, version, python, system, machine):
    with pytest.raises(RuntimeError):
        local_package.build_from_dependency(dict(blender=version, python=python, system=system, machine=machine), 'source')
    builder_source[1].assert_not_called()


@pytest.mark.parametrize(('version', 'python'), [([5, 2, 1], '3.11'), ([99, 0, 0], '3.13')])
def test_detected_runtime_is_passed_to_builder_without_version_allowlist(builder_source, version, python):
    archive, kind, _ = local_package.build_from_dependency(
        dict(blender=version, python=python, system='Darwin', machine='arm64'), 'source')
    options = json.loads(archive.read_text())
    assert options['python'] == python
    assert options['blender_min'] == f'{version[0]}.{version[1]}.0'
    assert kind == 'extension'
    builder_source[1].assert_called_once()
