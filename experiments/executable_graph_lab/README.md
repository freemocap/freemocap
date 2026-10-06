# Parked experiment: executable pipeline graphs

**Status: experimental sidebar, not approved for application integration.**
Parked on 2026-10-06 so it can be reconsidered alongside the separate posthoc
pipeline work. Nothing in the application imports or launches this folder.
This folder is outside the packaged `freemocap` source and the application tests.
Do not treat it as the canonical posthoc architecture or merge it into the app
without reconciling that other work first.

## Contents

- `graph/`: real-data experiment, isolated worker, FastAPI server, WebSocket
  reports, executable graph definitions, and standalone HTML viewer.
- `checks/`: opt-in scheduling and transport checks, renamed to avoid normal
  `test_*.py` discovery.
- `synthetic/`: earlier dummy-data prototype, viewer iterations, contracts,
  handoff notes, and opt-in `checks_lab.py`. Historical README claims describe
  earlier iterations; they are not the current application architecture.
- `notes/architecture-history.md`: the full design write-up as it stood when
  parked, including this experiment's implementation notes. Historical paths
  identify where the work previously lived.
- `evidence/` (Git-ignored): screenshots, copied run reports/event logs, and an
  inventory pointing to the original generated runs. This evidence is local;
  it will not travel in a normal commit.

The larger generated datasets and copied model weights remain untouched in the
repository's ignored `.test-artifacts/graph-*` directories. They are data, not
application changes. The earlier synthetic prototype has been moved here from
the outer workspace's `.test-artifacts/executable-graph-lab` directory.

## What was useful

Typed input/output connections determine both executable dependencies and the
viewer graph. Camera partitions have separate progress bars. HTTP commands,
WebSocket reporting, bounded report queues, and a separate execution process
were exercised on real three-camera RTMPose data. No main application entry
point, dependency declaration, lockfile, or production coordinator was changed
by this experiment.

## Unresolved design issues

The graph mixes configuration inputs, resource initialization, long-lived reader
lifetimes, and per-frame processing as visually equivalent nodes. Node status
reflects instantaneous work rather than a stable stage lifecycle. Two-frame
read-ahead causes loading progress to extend across tracking and needs explicit
waiting/activity reporting. Observations accumulate until a final save. Task
variants, 3D, annotation, and admission alongside realtime GPU work are not
integrated. Performance results are exploratory, not controlled benchmarks.
Server/worker crash recovery and the main application's exact WebSocket schema
also need alignment. Transport isolation is useful progress, not evidence that
the overall pipeline design is ready.

## Opt-in checks

From the core repository root, with its existing environment:

```powershell
.venv/Scripts/python.exe -B -W ignore -m unittest -q `
  experiments.executable_graph_lab.checks.checks_runtime `
  experiments.executable_graph_lab.checks.checks_transport
```

For the earlier synthetic checks, change to `synthetic/` and run the same
interpreter with `-B -m unittest -q checks_lab`.

No server is started automatically. To deliberately reopen the real-data lab:

```powershell
.venv/Scripts/python.exe -B -m experiments.executable_graph_lab.graph.server `
  --output-root experiments/executable_graph_lab/runs --port 8767
```

See `graph/README.md` for the experimental protocol. Real adapters still use the
installed core environment and existing core APIs; this is not an independent
production package. Reports and outputs belong under ignored `runs/` or the
existing `.test-artifacts/` directory.
