"""Real exports from an empty normal profile; setup happens only inside export."""
import json
import os
from pathlib import Path
import tempfile
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from freemocap.api.http.blender.blender_router import blender_router
from freemocap.core.blender import preparation
from freemocap.core.blender.runtime import environment, inspect_blender
from freemocap.core.blender.package_catalog import digest
from freemocap.tests.test_blender_integration import test_prepared_recording_export

pytestmark = pytest.mark.e2e


@pytest.fixture(scope='module')
def installed_blender():
    from freemocap.tests.blender_test_dependency import install_dependency, seed_wheels
    blender = os.environ.get('FREEMOCAP_BLENDER_EXE')
    if not blender or not os.environ.get('FREEMOCAP_TEST_ADDON_WHEEL'):
        pytest.skip('Set Blender executable and the add-on Python wheel')
    with tempfile.TemporaryDirectory(prefix='fma-') as temporary, pytest.MonkeyPatch.context() as env:
        root = Path(temporary)
        install_dependency(root/'dependency', env)
        normal = root/'normal'
        for key, value in environment(normal).items():
            if key.startswith('BLENDER_USER_'):
                env.setenv(key, value)
        runtime = inspect_blender(blender)
        assert not runtime['packages']
        seed_wheels(root/'managed/wheels', runtime['python'])
        env.setenv('FREEMOCAP_BLENDER_STORAGE', str(root/'managed'))
        env.delenv('FREEMOCAP_BLENDER_PACKAGE_CATALOG', raising=False)
        env.delenv('FREEMOCAP_BLENDER_DEVELOPMENT_BUILD_HASH', raising=False)
        import urllib.request
        env.setattr(urllib.request, 'urlopen', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('offline: no release/catalog/download allowed')))
        app = FastAPI(); app.include_router(blender_router)
        yield TestClient(app), blender, None
        assert not inspect_blender(blender)['packages'], 'Normal profile was modified'
        assert not (normal/'config/userpref.blend').exists()
        assert len(list((root/'managed/profiles').glob('*.json'))) == 1
        assert len(list((root/'managed/built').glob('*/package.zip'))) == 1
