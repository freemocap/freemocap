"""Read export choices and published artifacts without composing playback."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from freemocap.core.recording.exports.arrays import data_channels
from freemocap.core.recording.exports.publication import ExportManifest, digest, published_artifact_path
from freemocap.core.recording.parquet_storage.channel_selection import ChannelSelection
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure


class ChannelOption(BaseModel):
    selection: ChannelSelection
    names: int
    components: list[str]
    units: dict[str, str]


class ExportRunOption(BaseModel):
    run_id: int
    channels: list[ChannelOption]


class RecordingExportOptions(BaseModel):
    revision: str | None = None
    selected_run_id: int | None = None
    kinds: tuple[str, ...] = ('channels', 'tall_csv', 'blender')
    formats: tuple[str, ...] = ('wide_csv', 'npy', 'npz', 'notebook')
    runs: list[ExportRunOption] = []


def export_options(structure: RecordingStructure) -> RecordingExportOptions:
    if not structure.data_parquet_path.is_file():
        return RecordingExportOptions()
    with recording_view(structure.data_parquet_path) as view:
        return RecordingExportOptions(revision=view.revision, selected_run_id=view.metadata.selected_run_id,
            runs=[ExportRunOption(run_id=run_id, channels=[ChannelOption(selection=context,
                names=len(channel.names), components=list(channel.components), units=channel.components)
                for context, channel, _ in data_channels(run)]) for run_id, run in view.metadata.runs.items()])


class PublishedArtifact(BaseModel):
    path: str
    format: str
    run_id: int | None = None
    source_revision: str | None = None
    manifest_path: str | None = None
    exists: bool
    integrity: Literal['unverified', 'valid', 'changed', 'missing'] = 'unverified'
    stale: bool | None = None


class ExportInventory(BaseModel):
    revision: str | None = None
    artifacts: list[PublishedArtifact] = []
    issues: list[str] = []


def plain_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and not getattr(path, 'is_junction', lambda: False)()


def export_inventory(structure: RecordingStructure, *, verify: bool = False) -> ExportInventory:
    """Hash checks are opt-in; a fast inventory never claims files are verified."""
    inventory = ExportInventory()
    if structure.data_parquet_path.is_file():
        try:
            with recording_view(structure.data_parquet_path) as view:
                inventory.revision = view.revision
        except (ValueError, OSError) as error:
            inventory.issues.append(f'Cannot read current recording revision: {error}')
    root = structure.exports_dir
    directories = []
    if root.exists():
        if plain_directory(root):
            directories = [root, *(path for path in root.glob('run-*') if plain_directory(path))]
        else:
            inventory.issues.append('Export directory is not an ordinary directory')
    known: set[Path] = set()
    for directory in directories:
        if (directory / '.publication.json').exists():
            inventory.issues.append(f'Publication incomplete in {directory}')
        manifests = sorted({*directory.glob('*_recording_info.json'), *directory.glob('*.metadata.json')})
        for path in manifests:
            try:
                if path.is_symlink():
                    raise ValueError('Manifest is a link')
                manifest = ExportManifest.model_validate_json(path.read_text(encoding='utf-8'))
                for artifact in manifest.artifacts.values():
                    target = published_artifact_path(directory, artifact.filename, artifact.location)
                    if target in known:
                        continue
                    known.add(target)
                    exists = target.is_file()
                    integrity = ('valid' if digest(target) == artifact.sha256 else 'changed') if exists and verify else 'unverified' if exists else 'missing'
                    inventory.artifacts.append(PublishedArtifact(path=str(target), format=artifact.format,
                        run_id=artifact.run_id, source_revision=artifact.source_revision, manifest_path=str(path),
                        exists=exists, integrity=integrity,
                        stale=artifact.source_revision != inventory.revision if inventory.revision else None))
            except (ValueError, OSError) as error:
                inventory.issues.append(f'{path}: {error}')
    # Blender and historical outputs may predate manifests. Discover them without
    # inventing a source revision or claiming integrity verification.
    roots = [structure.full_path, *(path for path in structure.full_path.glob('run-*') if plain_directory(path))]
    for directory in [*roots, *directories]:
        children = [directory, *(path for name in ('csv', 'npy', 'CSV', 'NPY') if plain_directory(path := directory / name))]
        for child in children:
            for path in sorted(child.iterdir()):
                if (path in known or not path.is_file() or path.is_symlink()
                        or path.suffix.lower() not in ('.blend', '.fbx', '.bvh', '.csv', '.npy', '.npz', '.ipynb')):
                    continue
                # Root CSV/NumPy files can be recording inputs, not exports.
                if child in roots and path.suffix.lower() not in ('.blend', '.fbx', '.bvh', '.ipynb'):
                    continue
                known.add(path)
                inventory.artifacts.append(PublishedArtifact(path=str(path), format=path.suffix[1:].lower(), exists=True))
    return inventory
