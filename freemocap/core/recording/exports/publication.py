"""Locked, recoverable multi-file export publication. Does not lock Parquet."""

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExportArtifact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str
    sha256: str
    rows: int = Field(ge=0)
    columns: tuple[str, ...]
    source_sha256: str
    source_revision: str
    run_id: int = Field(ge=0)
    format: Literal['tall_csv', 'static_tall_csv']

    @field_validator('filename')
    @classmethod
    def safe_filename(cls, value):
        if value in ('', '.', '..') or any(c in value for c in '/\\:'):
            raise ValueError('Export filename must be a single relative name')
        return value


class ExportManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    status: Literal['complete'] = 'complete'
    artifacts: dict[str, ExportArtifact]
    snapshots: dict[str, dict]
    csv: dict = Field(default_factory=lambda: dict(encoding='utf-8-sig', delimiter=',',
        null='empty field', float_precision='round-trip float64',
        text='Literal recorded identities; import text columns as text in spreadsheet software.'))


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def remove_staging(directory: Path, staging: Path) -> None:
    if (staging.is_symlink() or not staging.name.startswith('.staging-')
            or staging.resolve().parent != directory.resolve()):
        raise ValueError('Refusing to remove a directory outside export staging')
    shutil.rmtree(staging)


def verified_manifest(path: Path) -> ExportManifest:
    """A manifest is usable only when no publication is pending and all hashes match."""
    if (path.parent / '.publication.json').exists():
        raise ValueError('Export publication is incomplete; recover it before reading or exporting')
    manifest = ExportManifest.model_validate_json(path.read_text(encoding='utf-8'))
    for artifact in manifest.artifacts.values():
        target = path.parent / artifact.filename
        if target.is_symlink() or not target.is_file() or digest(target) != artifact.sha256:
            raise ValueError(f'Export file missing or changed: {artifact.filename}')
        if artifact.source_sha256 not in manifest.snapshots:
            raise ValueError('Export artifact has no source snapshot')
    return manifest


def finish_publication(directory: Path) -> None:
    """Caller holds export lock. Retry completes only the exact journaled files."""
    journal = directory / '.publication.json'
    data = json.loads(journal.read_text(encoding='utf-8'))
    stage_name = data['staging']
    if not stage_name.startswith('.staging-') or Path(stage_name).name != stage_name or any(c in stage_name for c in '/\\:'):
        raise ValueError('Invalid export staging directory')
    staging = directory / stage_name
    if staging.is_symlink():
        raise ValueError('Export staging must not be a link')
    for entry in data['files']:
        name = ExportArtifact.safe_filename(entry['filename'])
        target, pending = directory / name, staging / name
        if target.is_symlink() or pending.is_symlink():
            raise ValueError('Export files must not be links')
        if not pending.exists():
            if target.is_file() and digest(target) == entry['sha256']:
                continue  # A previous publication step completed before interruption.
            raise ValueError(f'Cannot recover missing export: {name}')
        if digest(pending) != entry['sha256']:
            raise ValueError(f'Staged export changed: {name}')
        if entry['no_clobber']:
            if target.exists():
                if digest(target) != entry['sha256']:
                    raise FileExistsError(f'Retained export already exists: {target}')
            else:
                os.link(pending, target)
            pending.unlink()
        else:
            os.replace(pending, target)
    journal.unlink()
    remove_staging(directory, staging)


def publish(directory: Path, staging: Path, manifest_name: str,
            manifest: ExportManifest, filenames: tuple[str, ...], keep: bool) -> None:
    write_json(staging / manifest_name, manifest.model_dump(mode='json'))
    files = [dict(filename=name, sha256=digest(staging / name), no_clobber=keep) for name in filenames]
    files.append(dict(filename=manifest_name, sha256=digest(staging / manifest_name), no_clobber=False))
    write_json(staging / 'journal.json', dict(version=1, staging=staging.name, files=files))
    os.replace(staging / 'journal.json', directory / '.publication.json')
    finish_publication(directory)
