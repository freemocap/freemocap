"""Recoverable replacement of local prepared recordings; caller holds prepare.lock."""

import json
from pathlib import Path
from uuid import uuid4


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def local_path(root: Path, path: Path) -> Path:
    """Never move an external directory or follow a junction during replacement."""
    root = root.resolve()
    path = path.absolute()
    if not path.resolve().is_relative_to(root) or path.resolve() == root:
        raise ValueError(f'Output path escapes its dataset directory: {path}')
    for item in (path, *path.parents):
        if item == root:
            break
        if item.exists() and (item.is_symlink() or getattr(item.stat(follow_symlinks=False),
                                                        'st_file_attributes', 0) & 0x400):
            raise ValueError(f'Refusing replacement through a filesystem link: {item}')
    return path


def recover(root: Path) -> bool:
    """Finish a completed save or restore the previous directory and ready marker."""
    journal = root / 'replacement.json'
    if not journal.exists():
        return False
    transaction = json.loads(journal.read_text(encoding='utf-8'))
    current = local_path(root, root / 'current')
    backup = local_path(root, Path(transaction['backup']))
    candidate = local_path(root, Path(transaction['candidate']))
    marker = root / 'ready.json'
    saved = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
    if saved == transaction['new'] and current.exists():
        journal.unlink()
        return True
    # candidate missing means it was moved into current before interruption.
    if current.exists() and not candidate.exists():
        retained = root / 'attempts' / ('interrupted-' + uuid4().hex)
        retained.parent.mkdir(exist_ok=True)
        current.rename(local_path(root, retained))
    if backup.exists():
        if current.exists():
            raise ValueError('Recovery found both previous and current results; inspect replacement.json')
        backup.rename(current)
    if transaction['old'] is not None:
        write_json(marker, transaction['old'])
    elif marker.exists():
        marker.unlink()
    journal.unlink()
    return True


def save_current(root: Path, candidate: Path, ready: dict) -> None:
    """Save the candidate, retaining a backup; rollback on error or next invocation."""
    if (root / 'replacement.json').exists():
        raise ValueError('Recover the interrupted save before replacing results')
    current = local_path(root, root / 'current')
    candidate = local_path(root, candidate)
    marker = root / 'ready.json'
    old = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else None
    if current.exists() != (old is not None):
        raise ValueError('Current results and ready.json disagree; inspect before processing')
    backup = root / 'history' / uuid4().hex
    backup.parent.mkdir(exist_ok=True)
    transaction = dict(old=old, new=ready, backup=str(backup), candidate=str(candidate))
    write_json(root / 'replacement.json', transaction)
    try:
        if current.exists():
            current.rename(local_path(root, backup))
        candidate.rename(current)
        write_json(marker, ready)
    except BaseException:
        recover(root)
        raise
    (root / 'replacement.json').unlink()
    if old is not None:
        # The previous marker lives beside its saved recording, with its path relocated.
        old = dict(old)
        old['recording'] = str(backup / Path(old['recording']).relative_to(current))
        write_json(backup / 'ready.json', old)
