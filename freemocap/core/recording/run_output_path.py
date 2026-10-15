"""Stable output names: ordinary Run 0 paths, separate folders for later runs."""
from pathlib import Path


def run_output_path(default: Path, run_id: int) -> Path:
    if run_id < 0:
        raise ValueError('Run IDs must be nonnegative')
    if run_id == 0:
        return default
    return default.parent / f'run-{run_id}' / f'{default.stem}.run-{run_id}{default.suffix}'
