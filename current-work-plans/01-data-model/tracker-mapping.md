# Tracker → Standard-Human Mapping

**Describes:** skellytracker's `*_to_standard_human_mapping.yaml` + `core.io` mapping machinery;
skellyforge's load-time completeness contract (`skellymodels/standard_human/tracker_contract.py`);
freemocap's mapping-path SSOT (`freemocap/core/tasks/mocap/tracker_mappings.py`).

## What this covers
The **one interface** between skellytracker (keypoints) and skellyforge (segments): the mapping YAMLs.
Tracker keypoints in → the named **landmarks** the segment model declares out (the mapping's output is
always a landmark; the production form — direct / weighted / offset — is the mechanism). Makes
skellyforge's output identical regardless of which tracker fed it.

## Key facts 
- Mapping forms: string / list (mean) / dict / **`anatomical_offset`** (a landmark built at an offset from
  tracked keypoints — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose).
- **Completeness contract:** skellyforge validates at load that a tracker mapping produces the full
  landmark set; a gap **raises** (the sanctioned lateral skellyforge→skellytracker import,
  base install only — see the workspace `CLAUDE.md` import rules).
- **Boundary rule (decided 2026-08-14):** the rest-pose/model side never imports skellytracker at
  runtime; the ONE sanctioned import is `tracker_contract.py` (the load-time completeness contract —
  base install, no detector extras). Shared anatomical ratios (face/mouth) are owned on the human side
  and pinned against the mappings by a **test**, not shared — see
  [`ontology.md`](../ontology.md)'s boundary section.

## Reconciliation notes
Files are `*_to_standard_human_mapping.yaml`; detector method `standard_human_mapping_path()`. The old
`tracker_info/*.yaml` files (still on disk, consumed only by the old model layer) die with it in the
posthoc rebuild, see [02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md). The mapping's
output is a **landmark**.
