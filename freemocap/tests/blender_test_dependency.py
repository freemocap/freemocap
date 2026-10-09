"""Install a built pure-Python wheel into a disposable distribution layout."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import zipfile


def install_dependency(destination, monkeypatch):
    destination.mkdir(parents=True)
    with zipfile.ZipFile(os.environ['FREEMOCAP_TEST_ADDON_WHEEL']) as wheel:
        assert not any('.data/' in name for name in wheel.namelist())
        wheel.extractall(destination)
    source = destination/'freemocap_blender_addon'
    assert (source/'_host_tools/build_addon.py').is_file()
    assert (source/'_host_tools/LICENSE').is_file()
    distribution = next(importlib.metadata.distributions(path=[str(destination)]))
    original = importlib.metadata.distribution
    monkeypatch.setattr(importlib.metadata, 'distribution',
        lambda name: distribution if name == 'freemocap_blender_addon' else original(name))
    return source


def seed_wheels(destination, python):
    """Preseed exact pinned binary inputs; network must not be needed afterward."""
    cache = Path(os.environ['FREEMOCAP_TEST_WHEEL_CACHE'])
    lock = cache/f'{python}-windows-x64.json'
    destination.mkdir(parents=True)
    shutil.copyfile(lock, destination/lock.name)
    for entry in json.loads(lock.read_text()):
        shutil.copyfile(cache/entry['filename'], destination/entry['filename'])
