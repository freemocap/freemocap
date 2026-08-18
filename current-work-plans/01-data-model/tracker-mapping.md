# Tracker → Standard-Human Mapping

**Describes:** skellytracker's `*_to_standard_human_mapping.yaml` + `core.io` mapping machinery;
freemocap's mapping-path SSOT (`freemocap/core/tasks/mocap/tracker_mappings.py`). The model is
**articulated**: a tracker hydrates the landmarks it can see (body + hand keypoints + `anatomical_offset`
derived points); the remaining landmarks (toes, condyles, deep points) ride the segment's rigid solve.

## What this covers
The **one interface** between skellytracker (keypoints) and skellyforge (segments): the mapping YAMLs.
Tracker keypoints in → the named **landmarks** the segment model declares out (the mapping's output is
always a landmark; the production form — direct / weighted / offset — is the mechanism). Makes
skellyforge's output identical regardless of which tracker fed it.

## Key facts 
- Mapping forms: string / list (mean) / dict / **`anatomical_offset`** (a landmark built at an offset from
  tracked keypoints — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose).
- **Boundary rule:** skellyforge **never imports skellytracker or freemocap**. The mapping is applied
  in freemocap (e.g. `biomechanics.tracker_mapping.apply(filtered_keypoints)` in the realtime
  aggregator) to turn tracker keypoints into standard-human landmarks before the rigidifier + solver.
  The old load-time "every landmark must be produced" completeness contract was removed — an articulated
  model is driven by the AVAILABLE tracker information, not a fixed full landmark set.

## Reconciliation notes
Files are `*_to_standard_human_mapping.yaml`; detector method `standard_human_mapping_path()`. The old
`tracker_info/*.yaml` files (still on disk, consumed only by the old model layer) die with it in the
posthoc rebuild, see [02-pipeline/posthoc-rebuild.md](../02-pipeline/posthoc-rebuild.md). The mapping's
output is a **landmark**.
