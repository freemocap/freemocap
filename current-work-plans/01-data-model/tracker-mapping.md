# Tracker → Standard-Human Mapping

> **Scaffold (2026-08-14) — pending ontology revision.** The keypoint→segment ontology is exactly what the
> upcoming discussion revises; hold full prose for it.

**Describes:** skellytracker's `*_to_standard_human_mapping.yaml` + `core.io` mapping machinery;
skellyforge's load-time completeness contract (`skellymodels/standard_human/tracker_contract.py`);
freemocap's mapping-path SSOT (`freemocap/core/tasks/mocap/tracker_mappings.py`).
**Salvage:** [`archive/streaming-compatibility-specs/13-tracker-to-canonical-mapping.md`](../archive/streaming-compatibility-specs/13-tracker-to-canonical-mapping.md)
(note: retitle — "landmark/canonical" retired).

## What this covers
The **one interface** between skellytracker (keypoints) and skellyforge (segments): the mapping YAMLs.
Tracker keypoints in → the named keypoints the segment model declares out. Makes skellyforge's output
identical regardless of which tracker fed it.

## Key facts (committed code)
- Mapping forms: string / list (mean) / dict / **`anatomical_offset`** (a derived point at an offset from
  a tracked one — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose).
- **Completeness contract:** skellyforge validates at load that a tracker mapping produces the full
  **76** required keypoints; a gap **raises** (the sanctioned lateral skellyforge→skellytracker import,
  base install only — see the workspace `CLAUDE.md` import rules).
- **Boundary rule (decided 2026-08-14):** the standard human is authoritative and **does not depend on
  the tracker**. Any shared anatomical ratio flows **tracker → human**, never human → tracker (see the
  S1 decision in [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)).

## Reconciliation notes
Files are `*_to_standard_human_mapping.yaml`; detector method `standard_human_mapping_path()`. The old
`tracker_info/canonical_*.yaml` are retired (removed with S2). Kill "canonical mapping" / "landmark".
