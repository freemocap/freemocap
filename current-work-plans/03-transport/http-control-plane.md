# HTTP Control Plane

> **Scaffold (2026-08-14) — needs a source-read pass before full prose.** The `/streaming/*` endpoints are
> not yet built/read; carried from the archived spec.

**Describes (target):** `freemocap/api/http/` — the `/streaming/*` control endpoints (list / start /
streams / stop) and the stream lifecycle.
**Salvage:** [`archive/streaming-compatibility-specs/04-http-control-plane.md`](../archive/streaming-compatibility-specs/04-http-control-plane.md).

## What this covers
The HTTP surface that drives streaming: enumerate targets, start/stop streams, query live streams —
scoped, fail-loud, **start idle**, **ephemeral** (server-side config not persisted).

## To capture when authored
- The endpoint set + payloads.
- The failure model (scoped fail-loud).
- Start-idle + ephemeral-config decisions.

## Reconciliation notes
Confirm which endpoints exist vs. planned before asserting; tag `[IN]`/`[LATER]` per
[IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).
