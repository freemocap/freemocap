# UI Integration

> **Scaffold (2026-08-14) — needs a source-read pass before full prose.** The decoder + renderer are
> landed and green (F3/F4), but I have not yet read the UI in depth; author fully after a read pass.

**Describes:** `freemocap-ui/src/` — `services/server/` (`ServerContextProvider`, the `transport/`
service, rolling-window stores) and `components/viewport3d/renderers/` (the rigid-body bone renderers,
keypoint/connection renderers).
**Salvage:** [`archive/streaming-compatibility-specs/05-ui-integration-and-refactor.md`](../archive/streaming-compatibility-specs/05-ui-integration-and-refactor.md),
[`archive/phase-1-work-plans/04-ui-wedge.md`](../archive/phase-1-work-plans/04-ui-wedge.md),
[`06-rigid-body-bone-renderer.md`](../archive/phase-1-work-plans/06-rigid-body-bone-renderer.md).

## What this covers
The frontend consumption of the standard stream: the transport service + standard-stream **decoder**
(golden-byte parity with the Python fixtures), rolling-window Redux stores, and the Three.js **rigid-body
bone renderer** driven by schema lengths + per-segment quaternions.

## Key facts (landed, green)
- F3 — transport service + decoder + wedge; F4 — rigid-body bone renderer (schema-driven lengths).
- 11 + 5 harness tests, `tsc` clean.

## To capture when authored
- `ServerContextProvider` decomposition + the transport service boundary.
- The rolling-window store shape (how samples index against the schema).
- The renderer: `RigidBodyBoneGeometry` / `RigidBodyBoneInstances` / `RigidBodyBoneRenderer` — how bones
  are placed from origin + quaternion + length.

## Reconciliation notes
`wxyz`; schema-driven; keypoint/segment vocabulary. Confirm the in-flight renderer edits before finalizing.
