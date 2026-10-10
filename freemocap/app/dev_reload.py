"""Opt-in source watcher; restart the complete backend after graceful shutdown."""

import asyncio
import os
from pathlib import Path
import signal
import sys
import subprocess
import tempfile
from threading import Event
import time
import traceback


def source_snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    result = {}
    for path in root.rglob('*.py'):
        if any(part in {'__pycache__', '.venv', '.test-artifacts'} for part in path.parts):
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue  # Editors can replace files atomically during a scan.
        result[path] = (stat.st_mtime_ns, stat.st_size)
    return result


class ShutdownFile:
    """One private, per-launch stop signal shared with a fresh interpreter."""

    def __init__(self, path: Path):
        self.path = path

    def is_set(self):
        return self.path.exists()

    def set(self):
        self.path.touch()

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while not self.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.05, remaining))
        return True


def _backend(stop):
    # Imported in a fresh interpreter on every restart, including on Windows.
    from freemocap.__main__ import main

    code = 0
    try:
        asyncio.run(main(reload_stop=stop))
    except KeyboardInterrupt:
        pass
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
    # Match __main__'s exit after worker/log cleanup; avoid queue finalizer hangs.
    os._exit(code)


def supervise(root: Path, *, command=None, stop: Event, interval=0.5, debounce=0.75):
    """Only restart after the previous child exits; never force-kill workers."""
    # A multiprocessing child cannot own SkellyCam pub/sub. A fresh interpreter
    # is the root of its own worker tree, exactly like a normal backend launch.
    command = command or [sys.executable, '-m', 'freemocap.app.dev_reload']
    signals = tempfile.TemporaryDirectory(prefix='freemocap-reload-')
    generation = 0
    previous = source_snapshot(root)
    pending_at = None
    process = None
    child_stop = None
    reported_failure = False

    def start():
        nonlocal generation
        generation += 1
        shutdown = ShutdownFile(Path(signals.name) / f'stop-{generation}')
        child = subprocess.Popen([*command, str(shutdown.path)])
        return child, shutdown

    def shutdown():
        if process is not None:
            child_stop.set()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                print('Waiting for backend workers to shut down; no replacement will start yet.', flush=True)
                process.wait()

    try:
        process, child_stop = start()
        while not stop.wait(interval):
            current = source_snapshot(root)
            if current != previous:
                previous = current
                pending_at = time.monotonic()
            if pending_at is not None and time.monotonic() - pending_at >= debounce:
                print('Python source changed; restarting backend (active jobs will stop).', flush=True)
                shutdown()
                process = None
                if stop.is_set():
                    break
                process, child_stop = start()
                pending_at = None
                reported_failure = False
            elif process.poll() is not None:
                if process.returncode == 0:
                    break  # An intentional app shutdown also stops the watcher.
                if not reported_failure:
                    print('Backend failed; waiting for a Python edit to retry, or Ctrl+C to exit.', flush=True)
                    reported_failure = True
    finally:
        try:
            shutdown()
        finally:
            signals.cleanup()


def run_reload():
    if getattr(sys, 'frozen', False):
        raise RuntimeError('Developer reload is unavailable in packaged applications')
    root = Path(__file__).resolve().parents[1]
    stop = Event()
    previous_handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[sig] = signal.signal(sig, lambda *_: stop.set())
        print(f'Developer reload: watching {root} for Python changes. Ctrl+C stops the backend.', flush=True)
        supervise(root, stop=stop)
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    _backend(ShutdownFile(Path(sys.argv[1])))
