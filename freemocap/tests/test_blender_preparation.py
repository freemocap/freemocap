"""Automatic setup policy, package integrity, and launch-profile boundaries."""
import json
import io
import hashlib
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from freemocap.core.blender import preparation, package_catalog, runtime
from freemocap.core.blender.export_to_blender import export_to_blender


def report(ready=False):
    return dict(blender=[5, 2, 2], python='3.13', machine='AMD64', system='Windows',
                package_details=[dict(package='bl_ext.local.freemocap_blender_addon', ready=ready, errors=['old build'])])


def test_matching_normal_profile_never_installs(monkeypatch):
    monkeypatch.setattr(preparation, 'inspect_blender', lambda *a, **kw: report(True))
    resolver = Mock(side_effect=AssertionError('must not resolve/download'))
    monkeypatch.setattr(preparation, 'resolve_package', resolver)
    result = preparation.prepare_blender('blender')
    assert result.profile is None
    resolver.assert_not_called()


def test_old_normal_profile_gets_managed_install_and_reuses_it(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, 'storage_root', lambda: tmp_path)
    monkeypatch.setattr(preparation, 'resolve_package', lambda *a: (tmp_path/'package.zip', 'extension', 'a'*64))
    monkeypatch.setattr(preparation, 'expected_build', lambda: dict(source_sha256='b'*64))
    monkeypatch.setattr(preparation, 'inspect_blender', lambda *a, profile=None, **kw: report(profile is not None))
    install = Mock(return_value=dict(package='bl_ext.local.freemocap_blender_addon'))
    monkeypatch.setattr(preparation, 'run_blender', install)
    first = preparation.prepare_blender('blender')
    second = preparation.prepare_blender('blender')
    assert first == second and first.profile.is_relative_to(tmp_path)
    assert install.call_count == 1
    assert install.call_args.kwargs['profile'] == first.profile


def test_failed_install_is_not_published(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, 'storage_root', lambda: tmp_path)
    monkeypatch.setattr(preparation, 'resolve_package', lambda *a: (tmp_path/'package.zip', 'extension', 'a'*64))
    monkeypatch.setattr(preparation, 'inspect_blender', lambda *a, **kw: report(False))
    monkeypatch.setattr(preparation, 'run_blender', lambda *a, **kw: dict(package='broken'))
    with pytest.raises(RuntimeError, match='failed verification'):
        preparation.prepare_blender('blender', development_build_hash='b'*64)
    assert not list((tmp_path/'profiles').glob('*.json'))
    # Retrying reaches verification again rather than retaining an installer lock.
    with pytest.raises(RuntimeError, match='failed verification'):
        preparation.prepare_blender('blender', development_build_hash='b'*64)


def test_catalog_refuses_wrong_download_before_install(tmp_path, monkeypatch):
    archive = tmp_path/'artifact.zip'; archive.write_bytes(b'corrupted')
    catalog = tmp_path/'catalog.json'
    catalog.write_text(json.dumps(dict(schema_version=1, packages=[dict(
        source_sha256='a'*64, blender='5.2', python='3.13', platform='windows-x64',
        sha256='b'*64, path='artifact.zip')])) )
    monkeypatch.setenv('FREEMOCAP_BLENDER_PACKAGE_CATALOG', str(catalog))
    monkeypatch.setenv('FREEMOCAP_BLENDER_STORAGE', str(tmp_path/'cache'))
    with pytest.raises(ValueError, match='checksum mismatch'):
        package_catalog.resolve_package(report(), 'a'*64)
    assert not list((tmp_path/'cache/packages').glob('*.zip'))
    with pytest.raises(RuntimeError, match='No unique developer'):
        package_catalog.resolve_package(report(), 'c'*64)


def test_export_and_open_share_managed_profile(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module('freemocap.core.blender.export_to_blender')
    blender = tmp_path/'blender.exe'; blender.touch()
    (tmp_path/'recording_data.parquet').touch()
    profile = tmp_path/'managed'
    monkeypatch.setattr(module, 'prepare_blender', lambda *a, **kw: preparation.PreparedBlender('managed.package', profile))
    def export(blender, request, *, profile):
        assert profile == tmp_path/'managed'
        assert request['package'] == 'managed.package'
        Path(request['output']).write_bytes(b'blend')
        return dict(output=request['output'])
    monkeypatch.setattr(module, 'run_blender', export)
    launch = Mock()
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    export_to_blender(tmp_path, blender_exe_path=blender)
    assert launch.call_args.kwargs['env']['BLENDER_USER_CONFIG'] == str(profile/'config')


def test_managed_environment_overrides_inherited_profile(tmp_path, monkeypatch):
    monkeypatch.setenv('BLENDER_USER_EXTENSIONS', 'normal/extensions')
    monkeypatch.setenv('PYTHONPATH', 'core-packages')
    env = runtime.environment(tmp_path)
    assert env['BLENDER_USER_EXTENSIONS'] == str(tmp_path/'extensions')
    assert 'PYTHONPATH' not in env


def test_catalog_download_then_offline_cache(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('build-info.json', json.dumps(dict(source_sha256='a'*64, export_api_version=1)))
    data = buffer.getvalue()
    catalog = tmp_path/'catalog.json'
    catalog.write_text(json.dumps(dict(schema_version=1, packages=[dict(
        source_sha256='a'*64, blender='5.2', python='3.13', platform='windows-x64',
        sha256=hashlib.sha256(data).hexdigest(), url='https://example.invalid/package.zip')])) )
    monkeypatch.setenv('FREEMOCAP_BLENDER_PACKAGE_CATALOG', str(catalog))
    monkeypatch.setenv('FREEMOCAP_BLENDER_STORAGE', str(tmp_path/'cache'))
    response = io.BytesIO(data)
    response.geturl = lambda: 'https://example.invalid/package.zip'
    download = Mock(return_value=response)
    monkeypatch.setattr(package_catalog.urllib.request, 'urlopen', download)
    monkeypatch.setattr(package_catalog, 'validate_archive', lambda path, runtime: (path, 'extension'))
    first = package_catalog.resolve_package(report(), 'a'*64)
    download.side_effect = AssertionError('offline')
    assert package_catalog.resolve_package(report(), 'a'*64) == first
    assert download.call_count == 1
