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
Tracker keypoints in → the named **landmarks** the segment model declares out (the mapping's output is
always a landmark; the production form — direct / weighted / offset — is the mechanism). Makes
skellyforge's output identical regardless of which tracker fed it.

## Key facts (committed code)
- Mapping forms: string / list (mean) / dict / **`anatomical_offset`** (a derived point at an offset from
  a tracked one — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose).
- **Completeness contract:** skellyforge validates at load that a tracker mapping produces the full
  **76** landmarks; a gap **raises** (the sanctioned lateral skellyforge→skellytracker import,
  base install only — see the workspace `CLAUDE.md` import rules).
- **Boundary rule (decided 2026-08-14):** the rest-pose/model side never imports skellytracker at
  runtime; the ONE sanctioned import is `tracker_contract.py` (the load-time completeness contract —
  base install, no detector extras). Shared anatomical ratios (face/mouth) are owned on the human side
  and pinned against the mappings by a **test**, not shared — see
  [`ontology.md`](../ontology.md)'s boundary section.

## Reconciliation notes
Files are `*_to_standard_human_mapping.yaml`; detector method `standard_human_mapping_path()`. The old
`tracker_info/canonical_*.yaml` files are retired (still on disk, consumed only by the old model layer —
they die with it in the posthoc rebuild, see [02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md)).
"Canonical mapping" as a phrase stays retired; the mapping's output is a **landmark**.
