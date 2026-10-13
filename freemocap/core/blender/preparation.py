"""Automatic package preparation, isolated from the user's Blender preferences."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import tempfile
from concurrent.futures import CancelledError
from time import monotonic
from filelock import FileLock, Timeout

from .expected_build import expected_build
from .package_catalog import resolve_package, storage_root
from .runtime import inspect_blender, run_blender

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedBlender:
    package: str
    profile: Path | None = None


@contextmanager
def preparation_lock(path, cancelled=None):
    """OS-owned locks release on process exit, including crashes."""
    lock = FileLock(path, timeout=180)
    try:
        if cancelled is None:
            lock.acquire()
        else:
            started = monotonic()
            while True:
                if cancelled():
                    raise CancelledError('Blender preparation cancelled')
                try:
                    lock.acquire(timeout=min(0.2, max(0, 180 - (monotonic() - started))))
                    break
                except Timeout:
                    if monotonic() - started >= 180:
                        raise
    except Timeout as error:
        raise RuntimeError('Another Blender setup is in progress; retry when it finishes') from error
    try:
        yield
    finally:
        lock.release()


def ready_package(report, requested=None):
    candidates = [p for p in report.get('package_details', []) if p['ready']
                  and (requested is None or p['package'] == requested)]
    return candidates[0]['package'] if len(candidates) == 1 else None


def prepare_blender(blender, package=None, development_build_hash=None, *, progress=None, cancelled=None):
    cancellation = {'cancelled': cancelled} if cancelled is not None else {}
    def report_progress(message):
        if cancelled is not None and cancelled():
            raise CancelledError('Blender preparation cancelled')
        logger.info('%s', message)
        if progress:
            progress(message)
    report_progress('Preparing Blender: checking installed FreeMoCap packages')
    report = inspect_blender(blender, development_build_hash, **cancellation)
    if installed := ready_package(report, package):
        return PreparedBlender(installed)
    target = development_build_hash or expected_build()['source_sha256']
    report_progress('Preparing Blender: preparing the package and its dependencies')
    archive, kind, checksum = resolve_package(report, target)
    key = hashlib.sha256((str(Path(blender).resolve()) + json.dumps(report['blender']) + checksum).encode()).hexdigest()[:24]
    profiles = storage_root() / 'profiles'
    profiles.mkdir(parents=True, exist_ok=True)
    pointer = profiles / (key + '.json')
    with preparation_lock(profiles / (key + '.lock'), **cancellation):
        if pointer.is_file():
            name = json.loads(pointer.read_text())['profile']
            if not name or name in ('.', '..') or Path(name).name != name:
                raise ValueError('Invalid managed Blender profile path')
            profile = profiles / name
            try:
                installed = ready_package(inspect_blender(blender, development_build_hash, profile=profile, **cancellation))
                if installed:
                    return PreparedBlender(installed, profile)
            except (RuntimeError, ValueError):
                logger.warning('Managed Blender profile failed verification; preparing a replacement')
        # Never overwrite an active profile: Blender can retain loaded binary DLLs.
        profile = Path(tempfile.mkdtemp(prefix=key[:8] + '-', dir=profiles))
        report_progress('Preparing Blender: installing FreeMoCap in its managed profile')
        result = run_blender(blender, dict(action='install', archive=str(archive), kind=kind), profile=profile, **cancellation)
        report_progress('Preparing Blender: verifying the installed package')
        verified = inspect_blender(blender, development_build_hash, profile=profile, **cancellation)
        installed = ready_package(verified, result['package'])
        if not installed:
            errors = [e for p in verified.get('package_details', []) for e in p['errors']]
            raise RuntimeError('Managed Blender installation failed verification: ' + '; '.join(errors))
        pending = pointer.with_suffix('.pending')
        pending.write_text(json.dumps(dict(profile=profile.name)), encoding='utf-8')
        pending.replace(pointer)
        return PreparedBlender(installed, profile)
