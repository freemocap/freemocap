# Python backend reload

From the core repository, use the existing environment:

```powershell
uv run --no-sync freemocap --reload
```

Equivalent commands: `python -m freemocap --reload`, running
`freemocap/__main__.py --reload`, or `uv run --no-sync poe dev-backend`.
The existing `freemocap` entry point handles the flag; no installation or new
dependencies are required. Normal launch without the flag stays unchanged.
Packaged PyInstaller applications reject `--reload`.

## PyCharm

Duplicate your existing Python backend Run Configuration and name it
**FreeMoCap — reload**. Keep its interpreter, working directory and script path
to `freemocap/__main__.py`; set **Parameters** to `--reload`.
Alternatively use module name `freemocap` with the same parameter.

Use **Run** for automatic reload. The backend runs in a child process; debugging
it requires PyCharm's subprocess debugging support. For ordinary breakpoint
debugging, the original configuration without reload is still available.

## Behavior

The watcher polls the core `freemocap/` package for Python edits, additions and
deletions. After saves settle, it requests the backend's normal shutdown, waits
for worker cleanup, and starts a fresh Python interpreter on the usual backend port. Each backend
is the root of its own multiprocessing worker tree, so it can create SkellyCam
pub/sub managers and subscriptions. A private temporary stop file carries the
shutdown request; the watcher removes these files when it exits.
It does not restart another already-running backend until you launch it; stop
your previous backend before starting this configuration.

Reload interrupts active recording, processing and export jobs. WebSockets
disconnect during restart and in-memory state is reset. There is no idle-job
deferral in this version. Ctrl+C stops the watcher and requests backend shutdown.
Use PyCharm's graceful stop where available; forced process termination can skip
cleanup, as it can with the normal backend.

If startup fails, the watcher remains available and retries after the next Python
edit. An intentional normal application exit also stops the watcher. A slow
worker shutdown delays replacement rather than launching overlapping backends.

Only core Python source is watched. Changes to installed dependencies, sibling
repositories, configuration files or frontend code do not trigger this watcher.
Generated exports, recordings and virtual environments outside the package are
not watched. No frontend launch settings are changed.

After updating the reload supervisor itself, stop and relaunch `freemocap --reload`
once. Source edits restart the backend, but do not replace the already-running
supervisor.
