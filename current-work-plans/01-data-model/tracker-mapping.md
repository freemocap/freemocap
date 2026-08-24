# Tracker → Standard-Human Mapping

**Describes:** skellytracker's `*_to_standard_human_mapping.yaml` + `core.io` mapping machinery
(`TrackerMapping`, `mapping_paths`); freemocap's mapping-path SSOT
(`freemocap/core/tasks/mocap/tracker_mappings.py`). The model is **articulated**: a tracker hydrates
the landmarks it can see (body + hand keypoints + `anatomical_offset` derived points); the remaining
landmarks (toes, condyles, deep points) ride the segment's rigid solve / transport.

## What this covers

The **one interface** between skellytracker (keypoints) and skellyforge (segments): the mapping YAMLs.
Tracker keypoints in → the named **landmarks** the segment model declares out (the mapping's output is
always a landmark; the production form — direct / weighted / offset — is the mechanism). Makes
skellyforge's output identical regardless of which tracker fed it. Four YAMLs ship today: mediapipe
body, mediapipe hand, rtmpose body, rtmpose hand.

## Key facts 

- Mapping forms: string / list (mean) / dict / **`anatomical_offset`** (a landmark built at an offset from
  tracked keypoints — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose).
- **Boundary rule:** skellytracker owns the YAMLs; skellyforge never imports skellytracker or freemocap;
  freemocap applies the mapping. Concretely: `load_standard_human_mapping(detector_type)` merges the
  body + hand YAMLs into one callable via `TrackerMapping.from_yaml`, and the aggregator runs
  `standard_human_mapping(filtered_keypoints)` → `{landmark_name: ndarray}` BEFORE hydration — tracker
  names become standard-human names before any model code sees them.
- There is no load-time "every landmark must be produced" contract — an articulated model is driven by
  the AVAILABLE tracker information. Detector-emittable points only: distal segments (metacarpals,
  phalanges beyond detector reach) are unmapped for now ("no metacarpals for now") and ride partial
  hydration / transported roll.

## Reconciliation notes

The offset ratios are generated against the rest pose, not hand-maintained:
`skellyforge/scripts/generate_tracker_mapping_ratios.py` regenerates them, and
`skellyforge/tests/test_tracker_mapping_offset_round_trip.py` fails when the YAML and the model
drift apart (a few frame-unreachable points carry explicit documented allowances).
`craniocervical_junction` hydrates from the ear mean — it authors at exactly `head_center`, so
the cervical segment follows the tracked head. The old skellyforge-side `tracker_info/*.yaml`
files are **deleted** (they died with the old system).
skellyforge's `test_tracker_mapping_boundary.py` validates every mapping-YAML key against the live
landmark set, so renames fail on the skellyforge side too. The mapping's output is a **landmark**.
