"""Record installed versions and read-only source revisions for a hardware run."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def capture_provenance() -> dict:
    packages = {}
    repositories = {}
    for name in ('freemocap', 'skellycam', 'skellycam_rust', 'skellytracker', 'skellyforge',
                 'numpy', 'opencv-contrib-python', 'onnxruntime-gpu', 'uvicorn', 'websockets'):
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        direct_url = distribution.read_text('direct_url.json')
        packages[name] = {'version': distribution.version,
                          'direct_url': json.loads(direct_url) if direct_url else None}
        if name not in ('freemocap', 'skellycam', 'skellytracker', 'skellyforge'):
            continue
        specification = importlib.util.find_spec(name)
        if specification is None or specification.origin is None:
            continue
        location = Path(specification.origin).resolve()
        packages[name]['module_path'] = str(location)
        if '.venv' in location.parts:
            continue
        root = next((parent for parent in location.parents if (parent / '.git').exists()), None)
        if root is None:
            continue

        def git(*arguments):
            return subprocess.check_output(['git', '--no-optional-locks', '-C', str(root), *arguments],
                stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=15)

        untracked = {}
        for filename in git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0'):
            if not filename:
                continue
            path = root / filename
            if path.is_file():
                untracked[filename] = {'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.stat().st_size <= 8_000_000 else None}
        repositories[name] = {'path': str(root), 'head': git('rev-parse', 'HEAD').decode().strip(),
            'status': git('status', '--porcelain').decode(),
            'tracked_diff_sha256': hashlib.sha256(git('diff', '--binary', 'HEAD')).hexdigest(),
            'untracked_files': untracked}
    return {'started_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
            'executable': sys.executable, 'platform': platform.platform(), 'packages': packages,
            'repositories': repositories}
