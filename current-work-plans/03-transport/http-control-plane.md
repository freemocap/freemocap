# HTTP Control Plane

**Describes (target):** `freemocap/api/http/` — the `/streaming/*` control endpoints (list / start /
streams / stop) and the stream lifecycle. **Not built yet** — this is the spec for the [LATER] streaming
control surface in [current scope](../README.md#next-work-in-order).

## What this covers

- The endpoint set + payloads.
- The failure model (scoped fail-loud).
- Start-idle + ephemeral-config decisions.

## To capture when authored

Confirm which endpoints exist vs. planned before asserting; tag `[IN]`/`[LATER]` per
[current scope](../README.md#next-work-in-order).
