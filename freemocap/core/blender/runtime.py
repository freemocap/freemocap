"""Host-side Blender boundary. Never expose core's Python packages to Blender."""
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from freemocap.core.blender.helpers.get_best_guess_of_blender_path import get_best_guess_of_blender_path

logger = logging.getLogger(__name__)
SCRIPT = Path(__file__).parent / 'helpers' / 'run_blender_export.py'


def executable(path=None):
    selected = path or get_best_guess_of_blender_path()
    if not selected or not Path(selected).expanduser().is_file():
        raise ValueError('Select an existing Blender executable in Blender settings')
    return Path(selected).expanduser().resolve()


def environment():
    result = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        result.pop(name, None)
    result['PYTHONNOUSERSITE'] = '1'
    result['PYTHONDONTWRITEBYTECODE'] = '1'
    return result


def run_blender(blender, request, timeout=900):
    blender = executable(blender)
    with tempfile.TemporaryDirectory(prefix='freemocap-blender-') as temporary:
        work = Path(temporary)
        request_path, result_path = work / 'request.json', work / 'result.json'
        request_path.write_text(json.dumps(request), encoding='utf-8')
        command = [str(blender), '--background', '--python-exit-code', '1',
                   '--python', str(SCRIPT.resolve()), '--', str(request_path), str(result_path)]
        result = subprocess.run(command, cwd=work, env=environment(), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, encoding='utf-8', errors='replace')
        logger.debug('%s', result.stdout)
        if result.returncode != 0 or not result_path.is_file():
            raise RuntimeError('Blender failed (exit {}):\n{}'.format(result.returncode, result.stdout[-8000:]))
        return json.loads(result_path.read_text(encoding='utf-8'))


def inspect_blender(blender=None):
    return run_blender(blender, dict(action='inspect'), timeout=120)
