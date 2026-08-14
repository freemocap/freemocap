# Current Work Plans

Engineering plans + design for the FreeMoCap **human-reconstruction rebuild** and its **LSL-shaped
streaming layer** — the two intertwined efforts that turn synchronized camera frames into a
self-describing stream of a canonical, VRM-1.0-aligned human.

> **Why this folder exists / how it's organized.** This started life as a single "streaming
> compatibility" spec, then absorbed a full rebuild of the human data model (segments, kinematics,
> tracker mappings). The two are now split **by architectural layer** (below). The old, jumbled,
> dual-numbered spec set (`00–14` + `phase-1/`) is preserved verbatim under [`archive/`](archive/) — it
> is history, not guidance. These docs are **built fresh from the committed code**; where they and the
> code disagree, the code wins and the doc is a bug.

## Layers (read in order)

| # | Layer | Covers |
|---|-------|--------|
| **00** | [foundation/](00-foundation/) | Conventions (frames, units, quaternions), the keypoint/segment vocabulary, testing philosophy — the facts every other layer assumes. |
| **01** | [data-model/](01-data-model/) | The canonical structures: the VRM segment model, T-pose reference geometry, tracker→standard-human mappings, and the stream schema/sample **types**. |
| **02** | [pipeline/](02-pipeline/) | The engine: kinematics (orientation solver, two-tier twist), segment-length estimation + fitting, the realtime loop, the posthoc path. |
| **03** | [transport/](03-transport/) | The wire: the standard-stream protocol, the backend encoder + WebSocket send-path, the streaming hub + LSL/VMC adapters, the HTTP control plane, on-disk serialization. |
| **04** | [ui/](04-ui/) | The frontend: transport service, rolling-window stores, the rigid-body renderers. |
| — | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | The one cross-cutting tracker: scope table + progress log. |

Single `00–04` numbering, one folder per layer, descriptive filenames. No `phase-1/`, no duplicate
numbers, no "which doc-11 do you mean."

## Status (2026-08-14)

The canonical human is **built and green**: skellyforge's 60-segment VRM 1.0 model (name-driven axes,
keypoint-driven solver, reference geometry, per-group rigid fit) — 147 tests. The freemocap realtime
backend (six-group schema, encoder, WebSocket reshape) and the freemocap-ui decoder + rigid-body
renderer are landed and green. Remaining: a small code tail (transport robustness, an old-model
diagnostic to retire), the **F5 full-loop gate** (tests + a manual run), then the posthoc rebuild.
Live scope + progress: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Canonical conventions (the one-liner; full form in [00-foundation/conventions.md](00-foundation/conventions.md))

**mm · right-handed · +Z up · +X forward**, quaternions **wxyz**, **identity == T-pose**,
`q_local = conj(q_parent) · q_child`. Segments are VRM 1.0 rigid bodies; the model is **60 segments /
76 required keypoints**.

## House rules for these docs

- **Single source of truth** — each fact lives in exactly one doc, cross-linked from the others. A fact
  stated twice is a bug.
- **Positive definitions** — a doc says what a thing *is*, not the infinite set of what it isn't.
- **Vocabulary** — keypoint / segment only. "Landmark" and "canonical" (as a mapping layer) are
  **retired**; if you find them outside `archive/`, that's a bug.
- **Code is truth** — these plans describe the committed code. Drift is a defect to fix, in the doc.
