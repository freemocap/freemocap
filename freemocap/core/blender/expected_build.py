"""Expected source is core's installed, pinned add-on, not Blender's installation."""
import importlib.metadata
import json
import sys
from pathlib import Path
from .helpers.addon_identity import source_hash


def expected_build():
    if getattr(sys, 'frozen', False):
        # Captured when building Electron's backend; no checkout or distribution
        # metadata lookup is needed on the user's machine.
        return json.loads(Path(__file__).with_name('bundled-build.json').read_text(encoding='utf-8'))
    distribution = importlib.metadata.distribution('freemocap_blender_addon')
    root = addon_source()
    direct = json.loads(distribution.read_text('direct_url.json') or '{}')
    return dict(version=distribution.version,
                source_commit=direct.get('vcs_info', {}).get('commit_id'),
                source_sha256=source_hash(root), export_api_version=1)


def write_bundled_build(destination):
    identity = expected_build()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(identity, indent=2) + '\n', encoding='utf-8')
    return identity


def addon_source():
    if getattr(sys, 'frozen', False):
        return Path(__file__).with_name('addon_source') / 'freemocap_blender_addon'
    return Path(importlib.metadata.distribution('freemocap_blender_addon').locate_file('freemocap_blender_addon'))
