---
title: Documentation transition
sidebar_position: 1
mdx:
  format: md
plan_status: ongoing
plan_generated: "2026-09-10"
---

# Documentation transition

## Review checkpoint — 2026-09-10

The [ownership and streaming review](architecture-review.md) is ready for a focused
content review. Its companion communication reference is grounded in named source
files. The processing output-policy audit and broader SDK documentation remain pending.

## Scope

Organize the documentation before changing application behavior. Use the docs to
make ownership, contracts, and open decisions explicit. This work does not certify
that existing implementation already follows the intended architecture.

## Agreed direction

- Scope: one desktop user, one server, one client with independent lifetimes.
- The server owns long-lived camera groups, realtime pipelines, posthoc workers,
  execution, and authoritative observations of devices and files.
- Client state is disposable. Interpreting a server message must not depend on
  a previous message or the HTTP request that started the operation.
- HTTP commands express intent. Processing defaults to overwrite; append run is
  explicit. Strict idempotence is not required for every operation.
- Stream messages are fully self-describing for their declared scope. The UI creates or updates the
  appropriate representation from their contents.
- Newer authoritative observations replace cached server state. Local drafts
  and presentation choices remain client concerns.
- The client can discard views locally; fresh messages can recreate them. The server
  does not need completed-task history, and the client does not need saved dismissal IDs.
- No cross-restart command recovery or notification replay is promised. A disconnected
  client can retain its last display until fresh observations arrive.

These are architectural goals. An implementation audit must separately record
where the current code agrees or differs.

## Decisions still needed

| Topic | Question to resolve |
| --- | --- |
| Processing outputs | Does UI-to-disk behavior implement default overwrite and explicit append run? |
| Fresh observations | Can each message be interpreted alone after either side restarts? |
| Task completion | Where should completed-history replay be removed while keeping active worker ownership? |
| SDK scope | Which Python APIs, HTTP routes, stream contracts, and saved formats are public? |
| Ownership | Which contracts belong to FreeMoCap and which belong to a Skelly package? |

## Sequence

1. **Publish working material.** Separate reference navigation from work plans,
   preserve archives, and show lifecycle/provenance headers.
2. **Reconcile pages.** Use the disposition register. Record source paths,
   evidence, unresolved claims, and audit dates for each reviewed page.
3. **Write architecture decisions.** Establish ownership, independent lifetimes, command
   intent, and fully self-describing message scope with concrete examples.
4. **Rebuild reference docs.** Consolidate verified content into architecture,
   workflow guides, and explicitly scoped SDK reference. Archive displaced notes.
5. **Audit implementation.** Trace request → controller → processing → publication
   → client store → view. Make focused work plans for actual contract violations.

## First reconciliation priorities

| Material | Disposition and reason |
| --- | --- |
| Frontend/backend communication and state-management docs | Update after tracing TransportService ownership and current consumers. |
| API boundary and recording structure docs | Reconcile playback HTTP routes and canonical recording models/formats. |
| Pipeline lifecycle and progress plans | Reconcile dismissal and active ownership with the agreed no-history requirement. |
| Connection ownership and browser playback plans | Candidates for reference after checking actual route/lifetime behavior. |
| Geometry matching and diagnostics plans | Keep as working material; separate shared diagnostic contracts from matcher policy. |
| Foundation, skeleton, biomechanics, and mapping plans | Candidates for domain reference; determine package ownership first. |
| Centroidal proposals | Review section by section: the overview mixes implemented phases and planned work. |
| Existing guides and build/test docs | Retain, verify commands and workflows before labeling them audited. |
| Existing archive | Preserve as historical material; no wholesale technical rewrite. |

## Publication rules

Work-plan Markdown uses `mdx.format: md`; the shared DocItem wrapper supplies its
React header. Docusaurus supports this per-page parsing mode:
[Markdown formats](https://docusaurus.io/docs/markdown-features#mdx-vs-commonmark).

Set `plan_status` to `ongoing` or `archived`. Record `plan_generated`,
`plan_migrated`, and `plan_audited` as quoted ISO dates only when known. AI-generated
code carries a provenance comment; AI-generated documentation displays the existing
SkellyDocs banner. Dates describe the document, not a model training cutoff.

Build and check links before publishing. A successful build verifies the site, not
the scientific or architectural claims in its pages.
