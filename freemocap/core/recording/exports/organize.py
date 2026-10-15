"""Organize existing, verified exports without changing their scientific contents."""
import os
from pathlib import Path
import shutil
import tempfile

from filelock import FileLock

from freemocap.core.recording.exports.publication import (
    artifact_path, publish, remove_staging, verified_manifest,
)


def organize_exports(structure):
    root = structure.exports_dir
    if not root.exists():
        return []
    artifact_path(root, 'inventory.json')
    moved = []
    with FileLock(root / '.exports.lock', timeout=0):
        directories = [root, *sorted(p for p in root.glob('run-*') if p.is_dir())]
        for directory in directories:
            prefix = structure.recording_name + (f'.{directory.name}' if directory != root else '')
            for name in (f'{prefix}_recording_info.json', f'{prefix}.wide.metadata.json', f'{prefix}.metadata.json'):
                path = artifact_path(directory, name)
                if not path.exists():
                    continue
                manifest = verified_manifest(path)
                relocations = {}
                for old, artifact in manifest.artifacts.items():
                    folder = 'npy' if artifact.format == 'npy' else 'csv' if artifact.format.endswith('csv') else None
                    if folder and '/' not in artifact.filename:
                        relocations[old] = f'{folder}/{artifact.filename}'
                if not relocations:
                    continue
                staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=directory))
                try:
                    artifacts = dict(manifest.artifacts)
                    for old, new in relocations.items():
                        artifact_path(directory, new)
                        pending = artifact_path(staging, new)
                        pending.parent.mkdir(exist_ok=True)
                        with artifact_path(directory, manifest.artifacts[old].filename).open('rb') as source, pending.open('wb') as target:
                            shutil.copyfileobj(source, target)
                            target.flush()
                            os.fsync(target.fileno())
                        artifacts[new] = artifacts.pop(old).model_copy(update={'filename': new})
                    publish(directory, staging, name, manifest.model_copy(update={'artifacts': artifacts}),
                            tuple(relocations.values()), True)
                    moved.extend(str(directory / new) for new in relocations.values())
                finally:
                    if staging.exists() and not (directory / '.publication.json').exists():
                        remove_staging(directory, staging)
    return moved
