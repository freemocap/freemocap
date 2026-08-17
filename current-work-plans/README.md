# Current Work Plans

Engineering plans + design for the FreeMoCap **human-reconstruction rebuild** and its **self-describing
message stream** — the two intertwined efforts that turn synchronized camera frames into a
self-describing stream of a standard-human, VRM-1.0-aligned human.

> **How this folder is organized.** Split **by architectural layer** (below). Older spec sets (the
> `00–14` streaming-compatibility specs, `phase-1/`, and the message-model-cutover snapshot) are
> preserved verbatim under [`archive/`](archive/) — they are history, not guidance. These docs and the
> code are two faces of one design conversation — neither is authoritative on its own; where they
> disagree, reconcile (see House rules below).

## Layers (read in order)

**Start with [`ontology.md`](ontology.md)** — the seven-layer kinematic architecture, the now/future line, and the VMC Definition of Done. Then the layers below.

| # | Layer | Covers |
|---|-------|--------|
| **00** | [foundation/](00-foundation/) | Conventions (frames, units, quaternions), the keypoint/segment vocabulary, testing philosophy. |
| **01** | [data-model/](01-data-model/) | The standard-human structures: the VRM segment model, T-pose reference geometry, tracker→standard-human mappings, and the message contract. |
| **02** | [pipeline/](02-pipeline/) | The engine: kinematics, segment-length estimation, the realtime loop, the posthoc path. |
| **03** | [transport/](03-transport/) | The wire: the message protocol, the backend relay, the streaming hub + adapters, the HTTP control plane, on-disk serialization. |
| **04** | [ui/](04-ui/) | The frontend: the message dispatcher (TransportService), the client homes, the renderers, the test-suite plan. |
| — | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | The one cross-cutting tracker: scope table + progress log. |

## Status (2026-08-17)

The **first milestone is reached**: the full end-to-end pipeline works — cameras → keypoints → mapping →
length estimation + fit → orientation solve → self-describing frame message → transport → decode → 3D
rigid-body render. The wire is a self-describing CBOR stream of five kinds (`frame` / `log` /
`framerate` / `app_state` / `progress`); the frame is a fully self-describing document (convention +
cameras + models + instances + trackers + image). The schema-then-samples wire and its replace-kinds are
retired.

**The next iteration** returns the app to its prior functionality inside the new architecture, so the old
system can be removed entirely:

1. **Charuco revival** — bring charuco board tracking back up: skellytracker's charuco data → the
   standard-human model → display (2D overlay + 3D). Convert the dormant charuco overlay renderer +
   calibration to the self-describing system.
2. **Posthoc parity** — rebuild the posthoc mocap pipeline onto the new segment model + kinematics, so
   realtime (online, per-frame, damped) and posthoc (batch, unbounded window) share one model, one
   solver, one length estimator.
3. **Remove the old system** — with charuco + posthoc on the new architecture, excise the old skellyforge
   `managers`/`models` layer + the old posthoc imports.

Supporting workstreams (see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)): the VMC adapter, the
frontend test suite (planned specifically), the rotate-once-at-capture consolidation, and polish items.

## Conventions (the one-liner; full form in [00-foundation/conventions.md](00-foundation/conventions.md))

**mm · right-handed · +Z up · +X forward**, quaternions **wxyz**, **identity == T-pose**,
`q_local = conj(q_parent) · q_child`. Segments are VRM 1.0 rigid bodies; the model composition is
**60 segments / 76 landmarks** (single-sourced in the [glossary](00-foundation/glossary.md)).

## House rules for these docs

- **Single source** — each fact lives in exactly one doc, cross-linked from the others. A fact stated
  twice is a bug.
- **Positive definitions** — a doc says what a thing *is*, not the infinite set of what it isn't.
- **Vocabulary** — keypoint (measured) · landmark (segment-local point) · segment (oriented volume), per
  [ontology.md](ontology.md). "Canonical" as a *mapping layer* stays retired; the old vague "landmark
  *layer*" is retired, but the *term* `landmark` is **revived** with a precise meaning.
- **Reconcile, don't defer** — no single artifact (code, docs, conversation) is authoritative. Where they
  disagree, resolve what is *right* and fix whichever one is stale; never treat one as gospel.
- **Scope lives here, not in history** — the current iteration's scope is this README +
  [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); `archive/` and the progress log are history.
