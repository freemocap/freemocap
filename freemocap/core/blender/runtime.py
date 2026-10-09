"""Host-side Blender boundary. Never expose core's Python packages to Blender."""
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import threading

from freemocap.core.blender.helpers.get_best_guess_of_blender_path import get_best_guess_of_blender_path

logger = logging.getLogger(__name__)
SCRIPT = Path(__file__).parent / 'helpers' / 'run_blender_export.py'
_launch_lock = threading.RLock()


def start_external(command, **kwargs):
    """Do not let the frozen backend's DLL directory leak into Blender."""
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        return subprocess.Popen(command, **kwargs)
    import ctypes
    with _launch_lock:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        size = kernel.GetDllDirectoryW(0, None)
        previous = ctypes.create_unicode_buffer(size + 1)
        kernel.GetDllDirectoryW(len(previous), previous)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return subprocess.Popen(command, **kwargs)
        finally:
            if not kernel.SetDllDirectoryW(previous.value or None):
                raise ctypes.WinError(ctypes.get_last_error())


def run_external(command, *, timeout, **kwargs):
    if not getattr(sys, 'frozen', False):
        return subprocess.run(command, timeout=timeout, **kwargs)
    with start_external(command, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def executable(path=None):
    selected = path or get_best_guess_of_blender_path()
    if not selected or not Path(selected).expanduser().is_file():
        raise ValueError('Select an existing Blender executable in Blender settings')
    return Path(selected).expanduser().resolve()


def environment(profile=None):
    result = dict(os.environ)
    for name in ('PYTHONPATH', 'PYTHONHOME'):
        result.pop(name, None)
    result['PYTHONNOUSERSITE'] = '1'
    result['PYTHONDONTWRITEBYTECODE'] = '1'
    if getattr(sys, 'frozen', False):
        for name in ('LD_LIBRARY_PATH', 'LIBPATH'):
            original = result.pop(name + '_ORIG', None)
            result.pop(name, None)
            if original is not None:
                result[name] = original
        bundled = Path(sys._MEIPASS).resolve()
        for name in ('PATH', 'DYLD_LIBRARY_PATH'):
            if name in result:
                result[name] = os.pathsep.join(entry for entry in result[name].split(os.pathsep)
                    if entry and not Path(entry.strip('"')).resolve().is_relative_to(bundled))
    if profile is not None:
        profile = Path(profile).resolve()
        profile.mkdir(parents=True, exist_ok=True)
        result['BLENDER_USER_RESOURCES'] = str(profile)
        for variable, folder in [('BLENDER_USER_CONFIG', 'config'), ('BLENDER_USER_SCRIPTS', 'scripts'),
                                 ('BLENDER_USER_DATAFILES', 'datafiles'), ('BLENDER_USER_EXTENSIONS', 'extensions')]:
            directory = profile / folder
            directory.mkdir(exist_ok=True)
            result[variable] = str(directory)
    return result


def run_blender(blender, request, timeout=900, *, profile=None):
    from .expected_build import expected_build
    request = dict(request, expected=expected_build())
    blender = executable(blender)
    with tempfile.TemporaryDirectory(prefix='freemocap-blender-') as temporary:
        work = Path(temporary)
        request_path, result_path = work / 'request.json', work / 'result.json'
        request_path.write_text(json.dumps(request), encoding='utf-8')
        command = [str(blender), '--background', '--python-exit-code', '1',
                   '--python', str(SCRIPT.resolve()), '--', str(request_path), str(result_path)]
        result = run_external(command, cwd=work, env=environment(profile), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, encoding='utf-8', errors='replace')
        logger.debug('%s', result.stdout)
        payload = json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else None
        if payload and payload.get('error'):
            raise RuntimeError(payload['error'])
        if result.returncode != 0 or not result_path.is_file():
            output = result.stdout if len(result.stdout) <= 12000 else result.stdout[:8000] + '\n…\n' + result.stdout[-4000:]
            raise RuntimeError('Blender failed (exit {}):\n{}'.format(result.returncode, output))
        return payload


def inspect_blender(blender=None, development_build_hash=None, *, profile=None):
    return run_blender(blender, dict(action='inspect', development_build_hash=development_build_hash), timeout=120, profile=profile)
