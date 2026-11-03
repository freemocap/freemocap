"""Offline Blender integration inputs must match the actual Blender runtime."""
import json

import pytest

from freemocap.tests.blender_test_dependency import seed_wheels


@pytest.mark.parametrize(('system', 'machine', 'target'), [
    ('Darwin', 'arm64', 'macos-arm64'), ('Darwin', 'x86_64', 'macos-x64'),
    ('Windows', 'AMD64', 'windows-x64'), ('Linux', 'x86_64', 'linux-x64'),
])
def test_seed_wheels_selects_runtime_lock_not_windows_default(tmp_path, monkeypatch, system, machine, target):
    cache = tmp_path / 'cache'
    cache.mkdir()
    filename = f'example-{target}.whl'
    (cache / filename).write_bytes(b'target wheel')
    (cache / f'3.13-{target}.json').write_text(json.dumps([dict(filename=filename)]))
    monkeypatch.setenv('FREEMOCAP_TEST_WHEEL_CACHE', str(cache))
    destination = tmp_path / 'seeded'
    seed_wheels(destination, dict(python='3.13', system=system, machine=machine))
    assert (destination / filename).read_bytes() == b'target wheel'
    assert (destination / f'3.13-{target}.json').exists()
