"""Readiness is established inside Blender, independently of build matching."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyarrow
import pyarrow.parquet
import pytest

from freemocap.core.blender import runtime
from freemocap.core.blender.helpers import addon_identity


@pytest.fixture
def probe(tmp_path):
    spec = importlib.util.spec_from_file_location('blender_runner_test', runtime.SCRIPT)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    (tmp_path / '__init__.py').write_text('__version__ = "v2026.04.1041"\n')
    lock = json.dumps([dict(name='pyarrow', version=pyarrow.__version__)])
    (tmp_path / 'dependency-lock.json').write_text(lock)
    identity = dict(schema_version=1, source_hash_version=1, version='2026.4.1041', export_api_version=1,
                    source_sha256=addon_identity.source_hash(tmp_path), python=runner.sys.version.split()[0].rsplit('.',1)[0],
                    platform='windows-x64', dependency_lock_sha256=hashlib.sha256(lock.encode()).hexdigest())
    (tmp_path / 'build-info.json').write_text(json.dumps(identity))
    module = SimpleNamespace(__file__=str(tmp_path/'__init__.py'), __version__='v2026.04.1041', __freemocap_export_api__=True)
    dependency = SimpleNamespace(dependency_report=lambda: dict(pyarrow=pyarrow.__version__),
        require_module=lambda name: pyarrow, parquet_module=lambda: pyarrow.parquet)
    with patch.object(runner.importlib, 'import_module', side_effect=lambda name: dependency if name.endswith('.dependencies') else module), \
            patch.object(runner.platform, 'system', return_value='Windows'), \
            patch.object(runner.platform, 'machine', return_value='AMD64'):
        yield runner, identity, dependency


def test_matching_build_and_real_parquet_roundtrip_are_ready(probe):
    runner, identity, _ = probe
    result = runner.inspect_package('addon', identity)
    assert result['ready'] and result['build_match'] == 'expected', result


def test_same_version_different_source_requires_explicit_development_selection(probe):
    runner, identity, _ = probe
    expected = dict(identity, source_sha256='0'*64)
    result = runner.inspect_package('addon', expected)
    assert not result['ready'] and result['build_match'] == 'different'
    assert runner.inspect_package('addon', expected, identity['source_sha256'])['ready']
    assert not runner.inspect_package('addon', expected, '1'*64)['ready']


def test_dependency_failure_blocks_matching_and_development_builds(probe):
    runner, identity, dependencies = probe
    def missing(): raise ModuleNotFoundError('Missing pyarrow')
    dependencies.parquet_module = missing
    for override in (None, identity['source_sha256']):
        result = runner.inspect_package('addon', identity, override)
        assert not result['ready'] and 'Missing pyarrow' in result['errors']


@pytest.mark.parametrize('mutation', ['missing', 'changed', 'api', 'lock'])
def test_unverified_or_incompatible_packages_never_pass(probe, tmp_path, mutation):
    runner, identity, _ = probe
    if mutation == 'missing': (tmp_path/'build-info.json').unlink()
    if mutation == 'changed': (tmp_path/'__init__.py').write_text('# source changed')
    if mutation == 'lock': (tmp_path/'dependency-lock.json').write_text('[]')
    if mutation == 'api':
        (tmp_path/'build-info.json').write_text(json.dumps(dict(identity, export_api_version=999)))
    assert not runner.inspect_package('addon', identity, identity['source_sha256'])['ready']


def test_structured_error_survives_noisy_blender_shutdown(tmp_path):
    blender = tmp_path/'blender.exe'; blender.touch()
    def launch(command, **kwargs):
        Path(command[-1]).write_text(json.dumps(dict(error='Missing pyarrow')))
        return SimpleNamespace(returncode=1, stdout='registration noise'*1000)
    with patch.object(runtime.subprocess, 'run', side_effect=launch):
        with pytest.raises(RuntimeError, match='^Missing pyarrow$'):
            runtime.inspect_blender(blender)
