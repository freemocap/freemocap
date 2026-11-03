"""Source/frozen identity and local preparation contract."""
import importlib
import json
import os
from unittest.mock import Mock

import pytest

from freemocap.core.blender import package_catalog, runtime

identity_module = importlib.import_module('freemocap.core.blender.expected_build')


def test_frozen_identity_needs_no_installed_distribution(tmp_path, monkeypatch):
    expected = identity_module.expected_build()
    identity_module.write_bundled_build(tmp_path/'bundled-build.json')
    monkeypatch.setattr(identity_module, '__file__', str(tmp_path/'expected_build.py'))
    monkeypatch.setattr(identity_module.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(identity_module.importlib.metadata, 'distribution', Mock(side_effect=AssertionError('no Python environment')))
    assert identity_module.expected_build() == expected


def test_frozen_environment_excludes_backend_libraries(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(runtime.sys, '_MEIPASS', str(tmp_path/'bundle'), raising=False)
    monkeypatch.setenv('PATH', os.pathsep.join([str(tmp_path/'bundle'), str(tmp_path/'bundle/bin'), str(tmp_path/'system')]))
    monkeypatch.setenv('LD_LIBRARY_PATH', str(tmp_path/'bundle'))
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/system/libraries')
    result = runtime.environment()
    assert result['PATH'] == str(tmp_path/'system')
    assert result['LD_LIBRARY_PATH'] == '/system/libraries'


def test_default_resolver_builds_without_catalog(monkeypatch):
    from freemocap.core.blender import local_package
    monkeypatch.delenv('FREEMOCAP_BLENDER_PACKAGE_CATALOG', raising=False)
    build = Mock(return_value=('package.zip', 'extension', 'checksum'))
    monkeypatch.setattr(local_package, 'build_from_dependency', build)
    monkeypatch.setattr(package_catalog.urllib.request, 'urlopen', Mock(side_effect=AssertionError('no GitHub requests')))
    assert package_catalog.resolve_package({'blender': [5,2,2]}, 'source') == ('package.zip','extension','checksum')
    build.assert_called_once_with({'blender': [5,2,2]}, 'source')


@pytest.mark.parametrize('version,python,system,machine', [
    ([5, 2, 0], '3.13', 'Darwin', 'arm64'),
    ([5, 3, 0], '3.14', 'Linux', 'x86_64'),
    ([4, 4, 0], '3.11', 'Windows', 'AMD64'),
])
def test_runtime_reaches_package_builder(tmp_path, monkeypatch, version, python, system, machine):
    from freemocap.core.blender import local_package
    class BuilderReached(Exception):
        pass
    monkeypatch.setattr(local_package, 'storage_root', lambda: tmp_path)
    def reached(*args, **kwargs):
        raise BuilderReached
    monkeypatch.setattr(local_package.importlib.util, 'spec_from_file_location', reached)
    with pytest.raises(BuilderReached):
        local_package.build_from_dependency(
            {'blender': version, 'python': python, 'system': system, 'machine': machine},
            identity_module.expected_build()['source_sha256'])
