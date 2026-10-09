"""Versioned output readiness, separate from successful numerical processing."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from freemocap.core.recording.exports.publication import digest


class OutputArtifact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str
    sha256: str
    source_sha256: str
    source_revision: str
    run_id: int = Field(ge=0)
    sensor_group: str
    validator_version: Literal[1] = 1
    status: Literal['passed'] = 'passed'
    checks: dict


class OutputAcceptance(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    profile: Literal['standard', 'numerical']
    required: tuple[str, ...]
    artifacts: dict[str, OutputArtifact]


def required_outputs(profile: str) -> tuple[str, ...]:
    if profile == 'standard':
        return ('parquet', 'blender')
    if profile == 'numerical':
        return ('parquet',)
    raise ValueError(f'Unknown dataset output profile: {profile}')


def verify_outputs(recording: Path, validation: dict, *, require_complete: bool = True) -> OutputAcceptance | None:
    payload = validation.get('outputs')
    if payload is None:
        if require_complete:
            raise ValueError('Legacy numerical-only ready marker; run datasets export to validate complete outputs')
        return None
    report = OutputAcceptance.model_validate(payload)
    required = required_outputs(report.profile)
    if report.required != required or set(report.artifacts) != set(required):
        raise ValueError('Required output set disagrees with the acceptance profile')
    if require_complete and report.profile != 'standard':
        raise ValueError('Numerical-only preparation does not certify a complete standard run')
    source_hash = validation['parquet_sha256']
    for kind, artifact in report.artifacts.items():
        path = recording / artifact.path
        if (Path(artifact.path).is_absolute() or not path.resolve().is_relative_to(recording.resolve())
                or path.is_symlink()):
            raise ValueError(f'Output path escapes recording: {artifact.path}')
        if (artifact.source_sha256 != source_hash or artifact.source_revision != validation.get('source_revision', '')
                or artifact.run_id != validation['run_id'] or artifact.sensor_group != validation['sensor_group']):
            raise ValueError(f'Stale output source binding: {kind}')
        if not path.is_file() or digest(path) != artifact.sha256:
            raise ValueError(f'Required output missing or changed: {kind}')
    return report


def accept_outputs(recording: Path, validation: dict, *, profile: str, blender_checks: dict | None = None) -> dict:
    required = required_outputs(profile)
    filenames = dict(parquet=f'{recording.name}_data.parquet', blender=f'{recording.name}.blend')
    if digest(recording / filenames['parquet']) != validation['parquet_sha256']:
        raise ValueError('Parquet changed during output validation')
    artifacts = {}
    for kind in required:
        checks = blender_checks if kind == 'blender' else dict(frames=validation['frames'], rows=validation['rows'])
        if checks is None:
            raise ValueError(f'Missing content validation for {kind}')
        artifacts[kind] = OutputArtifact(path=filenames[kind], sha256=digest(recording / filenames[kind]),
            source_sha256=validation['parquet_sha256'], run_id=validation['run_id'],
            source_revision=validation.get('source_revision', ''), sensor_group=validation['sensor_group'], checks=checks)
    report = OutputAcceptance(profile=profile, required=required, artifacts=artifacts)
    result = dict(validation, outputs=report.model_dump(mode='json'))
    verify_outputs(recording, result, require_complete=profile == 'standard')
    return result
