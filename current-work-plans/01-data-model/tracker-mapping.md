# Tracker → Landmark Mapping

**Describes:** skellytracker's `*_to_*_mapping.yaml` + `core.io` mapping machinery
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
  tracked keypoints — e.g. `head_vertex`, `foot_ball`, `jaw`, mouth corners for RTMPose) / **pass-through**.
- **Measured vs. constructed.** Every non-offset form is an affine combination of measured keypoints
  with constant coefficients, so it carries the subject's real geometry; an `anatomical_offset` places
  a landmark at `ratio x reference_length` and therefore restates the template.
  `TrackerMapping.directly_measured_landmark_names` draws that line, and the model-scale fit only lets
  measured landmarks set the scale
  ([../02-pipeline/model-scale-fitting.md](../02-pipeline/model-scale-fitting.md)).
- **Pass-through** (`passthrough_keypoints_as_landmarks: true`) is the whole file for an object whose
  markers ARE its landmarks — a charuco board. Every keypoint becomes a landmark of the same name, so
  every landmark is measured. Authoring a line per marker would be duplication with a chance of typos,
  and it is the case that recurs for any simple tracked object.
- **Boundary rule:** skellytracker owns the YAMLs; skellyforge never imports skellytracker or freemocap;
  freemocap applies the mapping. Concretely: `load_standard_human_mapping(detector_type)` merges the
  body + hand YAMLs into one callable via `TrackerMapping.from_yaml`, and the aggregator runs
  `standard_human_mapping(filtered_keypoints)` → `{landmark_name: ndarray}` BEFORE hydration — tracker
  names become standard-human names before any model code sees them.
- There is no load-time "every landmark must be produced" contract — an articulated model is driven by
  the AVAILABLE tracker information. Detector-emittable points only: distal segments (metacarpals,
  phalanges beyond detector reach) are unmapped for now ("no metacarpals for now") and ride partial
  hydration / transported roll.

## Connected fitting: reuse the existing boundary

Reviewed against the implementation on 2026-09-24. The connected solver does not
need another tracker-to-skeleton mapping system.

- `TrackedSkeletonBundle.landmark_mapping` already supplies the mapping and its
  authored snapshots. `RecordedModel.mappings` persists those definitions; replay
  restores them without loading today's mapping YAMLs.
- Forge's `AnatomicalLandmark` already owns the segment name and local position.
  Its connected forward kinematics already produces predicted world landmarks.
  A target therefore refers to an existing landmark, not a second attachment table.
- `fit_connected_pose` already accepts landmark-keyed targets. Its current fixed
  root, per-frame rotation fitting is a limited prototype; it is not the planned
  recording-wide connected solve.

The missing piece is target selection and accounting for shared inputs. For
example, one shoulder keypoint supplies both shoulder and acromion landmarks.
Those are different model points backed by the same input, not two independent
measurements. Do not choose whichever name happens to occur first. Select the
model correspondence explicitly and preserve its source relationship using the
existing mapping snapshot. Means and offsets remain useful mapped landmarks;
they must not silently become additional independent positional evidence.

`directly_measured_landmark_names` is the existing scale-fitting classification:
it includes means and weighted combinations. It is not a list of independent
solver targets. Keep its scale-fitting meaning intact.

Next implementation order:

1. Verify recording/replay preserves the mappings and model attachments for both
   supported human trackers, including missing source points.
2. Specify the connected fit's selected existing landmarks and identify shared
   source inputs from the saved mapping definitions in FreeMoCap. Do not duplicate
   detector mappings in Forge or silently choose between distinct attachments.
3. Extend Forge's connected fitting using those landmark targets, its existing
   skeleton geometry and forward kinematics. Add root and sequence fitting as
   explicit solver work; retain mapped observations separately from predictions.
4. Integrate and persist the production result in FreeMoCap before displaying it
   as a new fitted skeleton in the recording viewer.

Observation-frame snapshot support is implemented in Forge. FreeMoCap's current
integration preserves old model fingerprints when that optional field is absent
and includes it when present. These changes do not change saved segment poses.

FreeMoCap now has `core/reconstruction/connected_fit_observations.py` for step 2.
It accepts an explicit landmark-to-tolerance selection, reads the bundle's mapping
snapshots, and produces Forge's existing `LandmarkTarget` values plus their source
keypoint names. Duplicate source use is rejected before checking frame availability.
Absent/NaN observations are omitted; malformed points and infinity fail. Direct
and prefixed pass-through mappings are supported; means and offsets cannot be
selected as independent targets. No default landmark selection or weights have
been introduced. This adapter is tested against both recorded human mappings but
is not yet called by production reconstruction. Source names are returned in
memory; no new Parquet output or metadata field has been introduced.

The upper-body prototype selection now lives beside the human bundle in
`standard_human_skeleton.py`: both hip sockets (pelvis), acromions (clavicles),
elbows (upper arms), wrists (forearms), ears and nose (skull). Those are 11 unique
source keypoints for both RTMPose and MediaPipe. Nose adds a non-collinear head
point to the ears. The current connected geometry places the upper-arm origin
at the acromion, so selecting both shoulder and acromion would duplicate that
input. This selection does not establish anatomical accuracy or remove the
spine/roll ambiguities; those still require explicit solver assumptions. No
production weights or optimizer settings are selected here.

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
