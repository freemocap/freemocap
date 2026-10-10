## Naming checkpoint and next PR work � 2026-10-10

Implemented export labels: `2d_overlay--<tracker>--<video>`,
`3d_keypoints_raw--<tracker>`, `3d_keypoints_filtered--<tracker>`,
`3d_landmarks--<model>`, `3d_segment_poses--<model>`. Recording/run prefixes and
lowercase format folders remain unchanged. CSV/NPY and NPZ keys agree. Canonical
Parquet identifiers remain unchanged. Regenerating a format retires its prior
verified filenames through normal publication; this is not source retention.

Latest inspected user recording: RTMW export at 2026-10-10T18:00:03Z, no escaped
headers, overlay confidence present, no retained export folders. The managed
export inventory contains RTMW rather than the previous MediaPipe products.

Next independently reviewable work, before declaring multi-tracker support:
1. Specify producer retention for canonical measurements and scientific exports:
   same producer replaces its previous result, different producer can coexist;
   current downstream reconstruction follows the selected producer. Split ChArUco
   measurements from the human tracker source. Define board/config identity and
   behavior for changed frame grids, including shared NumPy timing and NPZ contents.
2. Add a backend plan preview comparing requested settings/input signatures with
   saved stage provenance. Return reuse/rerun/missing/affected downstream stages
   with reasons. Existing execution-plan signature validation and dependency
   invalidation are a foundation, not a settings-reactive UI implementation.
3. Put replace-versus-retain-run controls beside the processing-stage selection,
   and show plan changes immediately when detector/calibration/filter settings
   change. Export-folder retention alone is not processing-run retention. Preserve
   manual rerun choices while preventing reuse of incompatible inputs.
4. Test RTM -> MediaPipe -> RTM, same-model reruns, explicit retained runs, changed
   timelines, and current downstream outputs; verify all selected export formats.

PR preparation for the current export checkpoint (can precede the larger work):
- Finish student-facing static format/folder README templates; explain axes,
  names, units, confidence, NaNs, and shared timing with loading examples.
- Resolve the confusing duplicate recording-info/export-inventory naming.
- Verify the standard-run reference acceptance includes Blender output and the
  selected scientific exports; explicitly report UI/Blender checks still pending.
- Review the accumulated diff and validation evidence, including unrelated dev
  reload changes separately. Human owns commits/pushes and PR publication scope.
- Keep new reprojection aggregation, landmark residuals, and exporter organization
  as explicit follow-up work, rather than implying they are finished.

## Quality output checkpoint � 2026-10-10

- Readable CSV headers preserve literal point names (`body.nose.x`), without URL escaping.
- CSV, NPY and NPZ overlay components use `confidence` for the saved `visibility`
  score. Preserve values and record original component labels in export metadata.
  This is an export-boundary alias, not a detector or canonical schema migration.
- Follow-up: raw 3D keypoint reprojection error. Saved diagnostics are per camera
  in pixels for the pixel-input route (normalized-coordinate diagnostics also
  exist; preserve declared units). Decide whether exports should expose camera-specific components
  or an aggregate (and which aggregate, camera inclusion and missing-data rules).
  Verify the diagnostic's raw/filtered provenance before attaching it to a point.
  Filtered positions must not inherit a raw-point error without verification.
- Follow-up: standard-human landmark residual. Compare saved reconstructed
  landmarks to saved MAPPED_KEYPOINTS_3D in the same model/reference frame; inspect
  the mapping for virtual/derived landmarks and missing observations. Establish
  whether scalar Euclidean distance in the coordinate units is the intended metric,
  then test it on known displacements and missing frames. Existing
  RIGID_BODY_RESIDUALS are measured segment-length deviations, not this metric.
- Keep quality-component semantics and ordering identical across CSV/NPY/NPZ.
  No fabricated error columns or new numerical calculations in this checkpoint.
- Defer exporter-module organization/refactor until the working checkpoint.

# Secondary recording exports

## Active checklist — 2026-10-09

Goal: a successful posthoc run produces and validates its selected outputs.
Parquet remains canonical. Wide CSV, standalone NPY and bundled NPZ are independent
selections; choosing one does not require the others. Each writer supports a
channel selection. Reference acceptance exercises every supported writer while
ordinary runs require only their selected outputs. A standard reference run
includes a validated Blender scene.

### 0. Finish Blender BVH integration

- [x] Add-on supports Blender-mediated BVH for both Parquet routes, including
  missing-sample handling and export/reimport checks. Human committed/pushed it.
- [x] Verify remote, checkout, core lockfile and installed add-on all resolve to
  `9cd37810354c59c2a1d5df77407101b4b496af6d`.
- [x] Remove core's legacy-only BVH validator, disabled toggle, explanatory text
  and reducer behavior that discarded BVH on route changes.
- [x] Validate core request forwarding and route switching: 14 focused backend
  tests, TypeScript checking, and the focused Edge browser test passed.
- [x] Human committed and pushed the core integration and reference-output checkpoint.

### 1. Make reference success cover actual outputs

- [x] Introduce versioned required-output profiles and structured per-output
  acceptance reports, independent of numerical-stage completion. Failed candidates
  retain their logs and cannot publish readiness; general job statuses follow in stage 5.
- [x] Enable Blender in the existing dataset producer, with no automatic GUI
  opening. Preflight the runtime/add-on before expensive processing.
- [x] Reopen the generated `.blend` in a fresh Blender process and validate its
  selected run, scene contents, timing, units and evaluated geometry against
  the same Parquet. Core owns the cross-package integration checks.
- [x] Publish complete-run ready markers only after required outputs pass;
  validate their source binding and artifact hashes on reuse. Recognize old
  numerical-only markers explicitly without deleting accepted user data.
- [x] Invalidate dependent exports after saved-stage processing and refresh;
  permit export-only retries while preserving numerical checkpoints.
- [x] Exercise missing Blender, failed export, stale files, cancellation and
  partial success; verify both reference recordings.

Normative details live in the
[complete-run acceptance contract](../../RECORDING_CONTRACT.md#complete-run-output-acceptance--owner-requirement-2026-10-09).
The dataset producer now implements the standard Parquet + Blender gate.
Scientific export writers and the application-wide job lifecycle remain below.

Validation on 2026-10-09: real calibration/tracking/reconstruction and native
Blender export completed on isolated copies of both reference recordings.
Fresh-process checks covered 222 and 1,108 frames, 124 landmarks and 61 segments;
13,110 and 65,192 finite segment poses respectively. Blender 5.2.2 used add-on
commit `9cd37810354c59c2a1d5df77407101b4b496af6d`. Position tolerance is 2 micrometers
and rotation-matrix tolerance is 0.00002. Both export-only retries passed with
the numerical worker disabled. All eight original input files retained their
hashes. Focused tests cover missing/stale outputs, source/run/group binding,
timeout/cancellation and retention of previously accepted results.
All four saved-scene acceptance tests passed, including independent landmark and
armature-transform corruption. Ruff and the whitespace diff check passed.

These checks certify the native saved-segment route. Wide CSV now has its own
validated csv/npy/NPZ consumer path described below; this does not claim
complete acceptance for arbitrary Blender cleanup/constraint routes or FBX/BVH.

### 2. Define selection and build one ordered-array reader

- [x] Typed export request: selected run/revision plus independent format jobs,
  each with explicit channel contexts or an all-available selection.
- [x] Resolve and freeze selection against one Parquet snapshot before writing.
  A context includes group, source, reference frame and channel, not just its label.
- [x] Return ordered values, frame numbers, timestamps, names, components, units
  and presence masks. Keep static data and distinct clocks separate.
- [x] Preserve measured keypoints and reconstructed landmarks as distinct data.
- [x] Reject duplicates/unknown selections, preserve null/absent distinctions,
  and use bounded-memory or disk-backed arrays for large contexts.
- [x] Verify scalar, XYZ, WXYZ, static, empty, irregular-frame and multi-source
  cases against source rows, including both real reference datasets.

### 3. Add wide CSV

- [x] One selected channel-context table per file: frame/timestamp columns then
  named scalar columns. Static tables remain separate.
- [x] Stable filenames, reversible headers and a metadata dictionary; split large
  tables without truncating them.
- [x] Reload and compare selected values/labels/timing/missingness against Parquet;
  record time, memory and file size. Add the writer to reference acceptance.
- [x] Turn automatic tall CSV off; keep explicit diagnostic export available.

### 4. Add standalone NPY and bundled NPZ

- [x] NPY: one values array per selected context, plus companion frame/time,
  name/component/unit metadata described by a JSON manifest. An NPY
  values file alone does not carry its scientific interpretation.
- [x] NPZ: one archive of the selected contexts and their companion arrays,
  embedding the manifest/descriptor so the archive is self-describing.
- [x] Both formats reuse the same array keys/order/shape contract. Typical 3D
  arrays are `(frames, keypoints_or_landmarks, 3)`; rotations use `(frames, segments, 4)`.
- [x] Use numeric/Unicode arrays, no objects or pickle. Verify loading with
  `allow_pickle=False`, exact identity/order and numerical comparisons.
- [x] Add NPY and NPZ consumers to reference acceptance as each writer lands.

### 5. Generalize publication, jobs and the posthoc Exports panel

- [x] Extend the currently tall-CSV-specific manifest/publication types for
  array/table artifacts and per-format source identity. Preserve older manifests.
- [x] Share the export service between after-processing and export-saved-result
  actions; bind automatic export to the run/revision actually produced.
- [x] Independent Wide CSV, NPY and NPZ controls, channel selection, persisted
  preferences, selected-run and retained-export controls.
- [x] Per-format progress/results, cancel and retry, open output folder; report
  numerical success separately from overall selected-output completion.
- [x] Browser/API tests cover format/channel selection, empty selections,
  route switching, saved-stage completion, failure and retry without reprocessing.

Publication type changes needed by writers are implemented with stages 3/4;
this stage completes lifecycle and user-facing integration.

### 6. Complete workflow acceptance and handoff

- [ ] Run both reference datasets through the producer and all selected consumers.
- [ ] Validate default replacement, retained exports, stale/missing artifacts,
  cancellation, partial failures and original input hashes.
- [ ] Include Blender FBX/BVH export/reimport checks for supported requested
  outputs; retain route-specific expectations and documented missingness limits.
- [ ] Document formats, load examples and measured resource use; reconcile stale
  roadmap entries and present core's final human commit/push handoff.

### Owner corrections and current handoff — 2026-10-09

2026-10-10: exported NPY/NPZ presence masks removed by owner request. NumPy
uses NaN for both absent and explicitly null samples; masks remain internal
for source validation and CSV writing. Shared timeline files are implemented: one frames array and one timestamps
array per NumPy export set, with matching count/frame numbers/timestamps required
for every measurement array. Timestamp comparison permits only four float64 ULPs
of arithmetic roundoff, with the maximum difference recorded in export metadata.
The sample reference has 177 frames with roundoff differences between camera and
3D timing; there is no frame-count mismatch. Incompatible selections fail before publication.
The inspected recording now has nine values arrays plus two timing files (11 NPY
files); the NPZ shares the same pair. Measurement values are unchanged.

Follow-up folder correction: CSV and NPY files live in `csv/` and `npy/`
inside the default export root or retained run folder. NPZ and the compact
inventory stay at that root. Existing verified files can be reorganized with
`organize_exports`; it preserves data hashes and updates relative inventory paths.

All data exports are optional. Data and format selection are independent. Only
3D landmarks starts checked. Raw/filtered 3D keypoints, per-camera 2D keypoints,
and segment positions plus world quaternions start unchecked. Joint angles are
deferred. No new numerical methods are needed for these choices.

CSV, NPY and NPZ now consume those shared products. Camera files use existing video
basenames; other files use readable source names, with no hexadecimal IDs. Default
exports overwrite selected formats under `exports/`; explicit retention uses
`exports/run-<id>/` and run-qualified filenames, as already agreed.

Automatic diagnostic YAML and its dedicated output folder are removed. Root
recording-info JSON preserves capture data and adds a compact processed summary.
Export recording-info JSON contains compact interpretation and per-file provenance;
NPZ embeds equivalent descriptions. Full descriptor/per-scalar metadata duplication
is removed. See the [format guide](../../freemocap/core/recording/exports/README.md).

Current controls: `mocap-scientific-settings.tsx`, with data/format selection,
saved runs, file-count preview, keep/replacement, export after processing,
progress/cancellation/retry and output-folder access. The lower-level old context
selection remains accepted for compatibility; the UI exposes the agreed data list.

Validation: 52 focused backend checks, TypeScript checking and the Edge browser
interaction test passed. Both reference recordings passed independent csv/npy/NPZ
comparisons (222 and 1,108 frames), covering all nine supported source contexts.

Default CSV export on a copy of the user's 222-frame recording produces two tables
(human and board landmarks), a 32,784-byte export inventory and a 67,404-byte root
recording-info companion. The source Parquet hash remained unchanged.

The earlier measurements and all-available-default claims are superseded by this
scope. Complete-run reference profiles currently require Parquet and Blender;
scientific formats have an independent consumer acceptance test, and integrating
them into required-output profiles remains stage 6 work.

## Historical implementation plan — 2026-09-30

Superseded by the active checklist and owner corrections above.


The owner selected the next milestone: optional tall CSV, wide CSV and NumPy NPZ
exports from canonical saved Parquet, exposed in the post-hoc mocap panel's
existing **Exports** section. All artifacts live beneath the recording's
`exports/` directory. This plan supersedes the implementation order and open
format questions in the historical investigation below. Tall CSV backend/CLI,
snapshot reading, metadata and recoverable publication are implemented. Tall CSV
is available in the posthoc Exports panel, enabled by default after processing,
with a separate saved-run export action. Wide CSV and NPZ remain subsequent stages.

Folder ownership and provenance rules are defined in the maintained
[Recording contract](../../RECORDING_CONTRACT.md). Current implementation gaps
are recorded in the [audit](../03-transport/recording-folder-contract.md).
The agreed default/retained layout below replaces the initial unique-folder proposal.

The larger branch milestone is a complete post-hoc recording, canonical Parquet,
these optional data exports, and a working
connection to the existing Blender add-on. Blender adaptation follows this work.
BVH, glTF, additional fitting research, and standalone NPY files are deferred.
NPZ contains ordinary NumPy arrays; separate NPY files can be added later using
the same array contract.

### Shared selection and output contract

- Export one explicitly resolved run, defaulting to the recording's selected
  run. Initial UI exports the full run: all its groups and available channels,
  including original reconstruction and fitted channels when present. Advanced
  channel/time-range selection is deferred.
- Preserve recorded values, timestamps, frame numbers, names, components, units,
  coordinate references and scientific definitions. Export never filters,
  interpolates, fits, realigns, resamples or replaces missing measurements.
- Read metadata and numerical rows from one open Parquet snapshot. Reuse or
  extract `recording_view` into the storage layer rather than introducing a
  second snapshot implementation. Capture source revision and selected run.
  Reject an export-now request whose expected revision has changed.
- A channel context is `(run_id, sensor_group, source, reference_frame, channel)`.
  Sources and clocks remain distinct. Do not invent person IDs or an entity axis
  that the recording does not declare. Source identity belongs in the manifest.
- Export existing static channels and frozen scale-fit views separately, using
  `read_static_channels`; do not repeat static values at every frame.
- Stream tall output in batches. Build wide/NumPy output one context at a time;
  use disk-backed scratch arrays for large contexts. Never materialize the whole
  recording as Python row dictionaries. Duplicate sample/component identities
  are errors, not values to average or silently overwrite.

Default exports use simple filenames directly under `exports/`. Explicitly
retained exports use a run subfolder and run-qualified filenames:

```text
<recording-id>/exports/
    <recording-id>.tall.csv
    <recording-id>.static.tall.csv
    <recording-id>.landmarks.wide.csv
    <recording-id>.segment-rotations-world.wide.csv
    <recording-id>.npz
    <recording-id>.metadata.json
    run-0/
        <recording-id>.run-0.tall.csv
        <recording-id>.run-0.landmarks.wide.csv
        <recording-id>.run-0.npz
        <recording-id>.run-0.metadata.json
```

Only selected formats are written. Wide/static table qualifiers describe their
content, with additional group/source qualifiers where required for uniqueness.
Default filenames do not imply run zero: metadata records the actual selected run.
An explicit retained export is protected from normal export replacement. An
existing retained destination must not be silently overwritten or mixed with a
different revision of the same run. Export retention does not allocate a new run.

`<recording-id>[.run-<id>].metadata.json` combines a versioned export manifest and
the exact embedded recording descriptor snapshot. The manifest records selection,
source revision/content hash, software version,
format outcomes, files, context identities, axis/column dictionaries, units and
missing-value conventions. Hash the same open snapshot used for data reading.
Filesystem-safe readable filename suffixes have deterministic collision handling;
full context identities remain in metadata. Track descriptor/revision/hash per
artifact so replacing one format cannot relabel an older unselected format.

Write to unique staging beneath `exports/`, then publish completed artifacts by
same-filesystem replacement for defaults and no-clobber publication for retained
outputs, under an export lock. Selected default formats replace their older files;
unselected formats remain with their original provenance. Multi-file replacement
is not atomic as a set: hashes/publication status must detect incomplete updates.
A manifest lists only
complete files as successful. Each format has a separate outcome; one writer's
failure must not discard another format's successful output. Cancellation stops
remaining work and cleans only owned incomplete artifacts. Export never changes
Parquet, capture metadata, or scientific processing checkpoints.

### Tall CSV

`<recording-id>[.run-<id>].tall.csv` uses the exact Parquet field names and order:

```text
timestamp_s,sensor_group,frame_number,source,reference_frame,channel,name,component,value,units,run_id
```

Write the selected run's existing rows without pivoting or expanding static data.
Use normal CSV quoting, decimal points and round-trip float64 precision. Null
values/reference frames are empty fields. Use UTF-8 with BOM for Excel. Preserve
text identities without automatic date or number conversion by the exporter.

`<recording-id>[.run-<id>].static.tall.csv` has `sensor_group,source,reference_frame,channel,name,component,value,units,run_id`;
there is no fabricated timestamp or frame number. Record its schema explicitly.
Tall files may exceed spreadsheet row limits; they remain full scientific exports.
Both CSV files are emitted, including a header-only static file when no static
values exist. Replacing an export therefore never leaves an older static table
appearing current. See the [export usage guide](../../freemocap/core/recording/exports/README.md).

### Wide CSV

One table per channel context, with one row per recorded sample on that context's
clock. First columns: `frame_number,timestamp_s`. Each subsequent column is one
named scalar, for example `left_wrist.x,left_wrist.y,left_wrist.z`. Quaternion
columns explicitly use `w,x,y,z`. Scalar channels retain their component label.
Use the recorded name/component ordering; do not sort anatomical labels alphabetically.

Escape literal dots/backslashes in labels so headers are reversible; validate
uniqueness. The manifest maps every column to its exact name, component and units.
Context identity is in the filename/manifest rather than repeated in every header.
Static tables use one row per name and one column per component.

Missing numerical cells are empty. If a declared item/component has no row at a
sample, leave its cell empty and preserve the distinction from explicit nulls in
the NPZ presence mask. Contexts with no samples produce headers and an explicit
zero-sample manifest entry. Never join independent clocks by frame number.

For Excel-sized output, split tables exceeding 1,048,575 data rows or 16,382
value columns into numbered parts, repeating the time/frame columns. The manifest
records the row/column ranges for every part; no data are silently truncated.

### NumPy NPZ

One archive contains independently described arrays for every context. The normal
dynamic shape is `(sample, name, component)`, including scalar channels with a
component axis of length one. Examples:

- 3D points: `(frames, landmarks_or_keypoints, 3)` with components `x,y,z`.
- Rotations: `(frames, segments, 4)` with components `w,x,y,z`.
- 2D observations: one camera/source context per array, retaining all declared
  components, including confidence/visibility when stored.
- Scalar quantities: `(frames, names, 1)` when one component is declared.
- Static quantities: `(names, components)`, with no synthetic time axis.

Per dynamic context, save `<id>_values` (float64), `<id>_frame_numbers` (int64),
`<id>_timestamps_s` (float64), `<id>_names` (Unicode), `<id>_components` (Unicode),
`<id>_units` (Unicode, aligned with components), and `<id>_present` (boolean, same
shape as values). Null or absent values become NaN; `present` distinguishes an
explicitly stored null from an absent row. Finite validity is `np.isfinite(values)`.
Static contexts have values/names/components/units arrays without frame/time arrays.

Embed scalar Unicode strings `manifest_json` and `metadata_json` inside the NPZ.
The manifest describes every array key, shape, dtype, axis meaning, label-array
keys, context identity, unit convention and missing-value policy. It must be
possible to understand the archive without its neighboring files:

```python
with np.load(path, allow_pickle=False) as data:
    description = json.loads(data['manifest_json'].item())
```

No object arrays or pickled Python values. No artificial common array shape for
different sources, lengths, clocks or component sets. Stream arrays into the NPZ
archive where practical rather than accumulating every context in memory.

### Post-hoc panel and execution

Extend `mocap-setup-modal.tsx`'s existing Exports section with independent
**Tall CSV**, **Wide CSV**, and **NumPy (.npz)** checkboxes, initially off. Show
the destination beneath the selected recording. Preserve the existing Blender
controls in the same section, with their current capability restrictions.

Checked formats run after successful processing/publication. Add **Export saved result** for the selected saved run,
without requiring videos, calibration, detector readiness or reprocessing.
Provide an explicit saved-run selector when multiple runs exist. Disable this
action when no saved result or no format is selected, with an explanatory label.

Provide an explicit **Keep export for this run** option targeting `exports/run-<id>/`;
default automatic exports use the simple root filenames. This option preserves
exports, not a new processing run. Report retained-destination conflicts explicitly.

Persist format preferences with mocap settings; pass one typed export-options
object through TypeScript request construction and Python configuration. Reuse
the post-hoc task lifecycle where appropriate, with an independent export task
and per-format outcomes. Show queued/running/completed/failed/cancelled status,
progress, useful error messages and an open-exports-folder action.

Processing success remains distinct from export success. Export failures must
not enter the mocap worker's general failure handler. Automatic exports capture
the actual published run/revision, not whichever run happens to be selected
later. Full and saved-stage processing paths must both reach the export trigger;
the current worker has early returns on saved-stage paths. Cancelled/failed
processing does not automatically start exports. Existing successful checkpoints
remain exportable manually after a later optional fit failure.

### Implementation stages and acceptance

At each stage, pair focused structural tests with consumers of the existing
production dataset workflow. Use fresh test/sample processing and its verified
ready markers as the integration baseline, then work on copies of those Parquet
files. The [reference acceptance guide](../../freemocap/tests/reference_recordings/README.md)
documents the producer/replay chain. Real-data acceptance is incremental throughout
implementation, as well as a final milestone check; it is not deferred to stage 4.

0. **Recording contract alignment (FreeMoCap).** Complete the path/provenance
   decisions and bounded changes in the recording folder contract before wiring
   exports into processing. Preserve legacy readers and distinguish unknown
   historical settings from execution-time defaults. No recording migration.
1. **Snapshot, contracts and tall CSV (FreeMoCap).** Implement the typed request,
   manifest, context inventory, coherent snapshot reader, static export and atomic
   publication. Test exact rows/metadata, float precision, nulls, run selection,
   mixed clocks, cancellation, source revision changes and failure preservation.
2. **Shared array reader, wide CSV and NPZ (FreeMoCap).** Reuse one pivot/ordering
   implementation. Test round trips, scalar/XYZ/WXYZ/static shapes, two sources
   with overlapping names, empty channels, irregular frames, explicit-null versus
   absent rows, escaped labels, part splitting and standalone NPZ descriptions.
   Verify `allow_pickle=False` and bounded processing on a real sample recording.
3. **Task/API and post-hoc UI (FreeMoCap).** Add export-now and after-processing
   using the same backend service. Test selection persistence, request mapping,
   full/saved-stage triggers, independent format failures,
   cancellation and unchanged successful mocap status. Run TypeScript checks and
   browser interaction checks for the actual Exports section.
4. **Reference acceptance and handoff (FreeMoCap).** Export both prepared datasets,
   reload csv/NPZ and compare all selected scientific values and identities to
   source Parquet. Inspect representative wide tables for readability. Confirm
   zero detection/reconstruction calls, source hashes unchanged, repeated default
   exports safely replaced, retained exports protected, and all artifacts beneath
   `exports/`. Document use and limitations.
   Present diffs/checks for the human-owned commit/push handoff before downstream
   Blender integration.

Before tests or generated examples, check the owning repository's ignore rules;
use ignored `.test-artifacts/` recording copies or external temporary directories.
Do not modify canonical prepared recordings as part of export testing. No new
dependency installation or cross-repository change is anticipated for this work.

## Historical investigation — 2026-09-22

Status: investigation and proposal, 2026-09-22. No implementation or format decisions are approved by this document.

Follow-up numerical evidence (2026-09-23): [saved hierarchy findings](secondary-export-hierarchy-findings.md).
The prepared test recording was inspected without reprocessing. This is the numeric
part of the evidence spike only; no BVH/glTF prototype or Blender import was performed.

## Assessment

The current Parquet contract appears to contain the ingredients for data exports and animated scene exports. csv/NumPy are comparatively straightforward. glTF visual playback is moderate work. A conventional BVH rig with demonstrated equivalence to playback is the highest-risk part: stored segment positions are not automatically the positions produced by a fixed-offset joint hierarchy.

The first milestone should prove that relationship on a saved recording before building all the controls. This investigation inspected code; it did not export a recording or verify an import in Blender.

## Current code and evidence

- `freemocap/core/tasks/mocap/posthoc_mocap_task.py`: triangulation, alignment, trajectory filtering, reconstruction, then `publish_posthoc_observations`. Successful completion publishes canonical Parquet.
- `freemocap/core/recording/sample_encoding/arrow_schema.py`: scalar long rows: `timestamp_s, sensor_group, frame_number, source, reference_frame, channel, name, component, value, units, run_id`.
- `freemocap/core/recording/sample_encoding/reconstruction_samples.py`: landmarks, segment origins, world/local WXYZ quaternions, joint angles, residuals, and optional center of mass. Missing frames/components remain missing.
- `freemocap/core/recording/data_descriptors/recording_model.py`: saved skeleton and rest-pose snapshots, tracker mappings, and scientific definitions. Recording fits supply segment lengths/scales through static channel views in `parquet_reader.py`.
- `freemocap/core/recording/playback_queries.py`: `recording_view` binds metadata, revision, and samples to one open file. Reuse/extract that storage-level capability; avoid exporting through three-second playback windows or transport messages.
- `freemocap-ui/src/components/viewport3d/renderers/RigidBodyBoneInstances.ts`: executable transform is translation times absolute world rotation times primary-axis geometry rotation times scale. World rotation already includes rest orientation. Do not apply rest orientation twice; some renderer header comments are older than the implementation.
- `RigidBodyBoneGeometry.ts` and `RigidBodyBoneRenderer.tsx`: tapered, flattened bone meshes, region-specific widths, side colors, fitted lengths, and missing-data hiding. GPU instances are updated per frame, not stored as animation clips.
- `ThreeJsScene.tsx`: bones, points, connections, face, cameras, axes, center of mass, and bloom. No trajectory-trail renderer was found in the inspected scene/source search.
- Sibling SkellyForge: `SkeletonPose.parent_relative_orientations` computes `inverse(parent_world) * child_world`; coordinate-system conversion, rest poses, scale fitting, and Euler math already exist. No active BVH/glTF writer was found in its core.
- Existing `/blender/export`, `export_to_blender.py`, and `BlenderSection.tsx` implement a separate MediaPipe-specific Blender/add-on path. They are not a generic Parquet export service.
- The setup modal already has an Exports section, currently containing Blender settings. `/posthoc/tasks` exposes existing task snapshots.

## Boundary proposal

```text
Published Parquet + embedded descriptor (one revision)
    -> FreeMoCap recording selection and array/table reading
        -> CSV / NumPy writers
        -> SkellyForge skeleton animation preparation
            -> BVH writer
            -> glTF scene writer + explicit presentation settings
    -> FreeMoCap artifact publication and job status
        -> API / CLI / UI
```

FreeMoCap owns recording paths, run/group/source/model selection, saved timestamps, revision validation, export jobs, progress/cancellation, output directories, and manifests. CSV and NumPy serialization belong alongside recording access: their schema is FreeMoCap's recording contract.

SkellyForge owns generic hierarchy/rest-frame math, scale-to-offset construction, world/local transform conversion, skeleton motion validation, resampling of poses, and BVH writing. A reusable skeleton glTF writer could also live there; recording-wide cameras, point trajectories, and viewport styling should remain in a FreeMoCap scene adapter unless a broader reusable scene API proves necessary. Keep FastAPI, React, Parquet layout, and recording folders out of SkellyForge.

Use existing skeleton/rest-pose/fit types. Introduce only the small animation input contract actually needed by both writers: names and parents, rest frames/offsets, sample times, transforms, and validity. Avoid creating a second scientific model.

Exports are downstream jobs, not reconstruction stages. An optional export-after-processing setting enqueues the same job only after publication succeeds. Export failure must not invalidate successful mocap results. Existing saved recordings must export without videos, calibration lookup, or detector execution.

## Format contracts to agree

| Format | Proposed first contract | Main difficulty |
| --- | --- | --- |
| Tall CSV | Selected canonical scalar rows, existing column names, original timestamps/units, empty field for missing value | Low; metadata and static values need companion files |
| Wide CSV | One row per sample on one sensor-group clock; separate files by source/channel/reference context | Low–moderate; naming, table size, explicit selection |
| NPZ | Named numeric arrays, timestamps, frame numbers, names/components, validity, plus JSON descriptor | Low–moderate; stable ordering and self-description |
| NPY | The same individual numeric arrays with a required manifest | Low; convenient for memory mapping, more files |
| BVH | Selected skeleton, fixed frame interval, hierarchy/offsets and ordered Euler channels | Moderate–high; hierarchy fidelity, gaps, Euler continuity |
| glTF / GLB | Named animated nodes and portable bone/point meshes; optional scene layers | Moderate; geometry/style parity, missing data, size |

CSV proposal: default tall. Preserve the exact selected descriptor in `metadata.json`; export static values as a separate table rather than silently repeating them per frame. Wide headers can be `left_elbow.x`, `left_elbow.y`, `left_elbow.z` inside a file scoped to a single source/channel/reference. Define escaping and collision checks, and provide a column dictionary mapping every header back to its full identity and units. Do not silently merge independent clocks, average duplicate keys, or mix channels in ambiguous headers. Split large selections deliberately for spreadsheet usability. CSV has no workbook sheets or formatting.

NumPy proposal: prefer NPZ as the packaged choice and offer NPY as advanced output. Use numeric arrays with `allow_pickle=False`; store descriptor text as JSON, not pickled Python objects. A spatial channel is `(samples, names, components)`; a quaternion channel has explicit `w,x,y,z` labels. Different sampling grids remain separate. Preserve float64 scientific values and null-to-NaN semantics, with explicit validity where useful. Filenames/array keys map to full identities through the manifest.

## BVH/glTF equivalence is the key investigation

Let saved segment world transforms be `(R_i(t), p_i(t))`. For child i with parent j:

```text
R_local_i(t) = inverse(R_j(t)) * R_i(t)
p_local_i(t) = inverse(R_j(t)) * (p_i(t) - p_j(t))
```

These local transforms reproduce the saved world transforms. However, a conventional root-translation-only BVH uses a constant child OFFSET rather than arbitrary `p_local_i(t)`. Measure the variation and forward-kinematics position error on real data, including branching attachments. Segment lengths alone do not define all attachment offsets.

Two explicit profiles may be needed:

1. **Recorded motion:** retain time-varying local translations (or independent world nodes in glTF). BVH can contain non-root translation channels, but target importer behavior must be tested. This best preserves the saved segment transforms.
2. **Fixed-offset rig:** use a fitted rest hierarchy, root translation, and joint rotations. If positions differ, this is an approximation or a separate rig-fitting operation. Report the error; never silently label it identical to playback. Any new kinematic projection/IK belongs in SkellyForge.

BVH also needs deterministic hierarchy order, name mapping, leaf End Sites, target units/axis convention, Euler order in degrees, and temporal continuity through angle wrapping/singularities. Stored biomechanical joint angles must not be blindly copied into BVH channels: their definitions need not match the export joint frames.

For a paired equivalence export, both writers consume the same prepared motion, gap policy, time range, and uniform sampling grid. Compare imported world transforms at corresponding sample times. Quaternion and Euler interpolation can differ between samples, so sampled equivalence is the initial promise, not identical continuous curves in every application.

## glTF scene scope

Prefer GLB as the convenient single-file packaging, while supporting the requested `.gltf` plus `.bin` form from the same writer. glTF supports node translation/rotation/scale animation; it uses meters and XYZW quaternions. Convert the recording basis and units at the writer boundary. See the [Khronos specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).

Start with named segment nodes, bone meshes and landmark markers. Keep geometric length/radius scale on mesh children so it cannot distort descendant joint transforms. Share mesh data where possible, but use ordinary animated nodes initially for importer portability. Add a skin/joint structure if editable Blender armature import is part of the acceptance contract; animated mesh nodes alone do not establish that requirement.

Extract a versioned presentation recipe for geometry dimensions, side colors, point sizes, and included layers. Both playback and export should consume that recipe, or share golden transform/geometry fixtures across Python and TypeScript. Do not duplicate arbitrary renderer constants indefinitely.

The existing Three.js [GLTFExporter](https://threejs.org/docs/pages/GLTFExporter.html) is useful for a visual prototype, but takes explicit animation clips. Exporting the current scene does not record the per-frame instance updates or retrieve the entire recording. A production backend writer supports batch/CLI export and avoids dependence on an open viewport.

Optional later layers: cameras, axes, center of mass, connections/face, and trajectories. Define trajectories explicitly: static full paths versus animated trailing windows are different products. Start with selected static paths as portable tube meshes, with downsampling controls and breaks across invalid intervals. A growing/sliding trail needs additional animation design and can be expensive. Bloom, overlays, and identical Blender lighting are outside basic geometry/motion equivalence.

## Time, missing samples, coordinates

- csv/NumPy preserve original timestamps. BVH needs an explicit uniform FPS and pose resampling. glTF can retain original times when exported alone; paired exports share the BVH grid.
- Normalize animation time to zero and preserve original start time in the manifest. Do not infer timing solely from nominal video FPS when saved timestamps exist.
- Use linear position interpolation and quaternion-aware orientation interpolation with sign continuity. Never interpolate Euler channels as the primary resampling representation.
- csv/NumPy preserve missing values. Animation export requires a declared policy: strict complete interval, split valid intervals, bounded interpolation, or explicit holding. Never synthesize identity rotations or origin positions silently. Hierarchy validity includes required ancestors.
- Metric calibrated recordings use millimeters; single-camera planar output is explicitly pixels in `SpatialReference`. Require an explicit scale for metric scene export or report it unavailable; do not relabel pixels as meters.
- Do not reapply saved alignment transforms to coordinates that were already aligned before publication.

## API and UI proposal

Provisional endpoint names; reconcile with the existing task manager before implementation:

- `POST /exports/preview`: resolve a recording path/identity plus revision, run, groups, sources/models, time range, formats, and options. Return capabilities, missing inputs, planned files, and resampling/gap consequences. Readiness depends on available channels, not detector brand.
- `POST /exports`: validate the same request, pin one source revision, enqueue a job, return 202 with job ID.
- `GET /exports/{job_id}` and `POST /exports/{job_id}/cancel`: progress, per-format outcomes, cancellation. Reuse existing task lifecycle/snapshot machinery where it fits.
- `GET /exports/{job_id}/artifacts/{artifact_id}`: download a published file by server-resolved artifact ID. Electron can also reveal the output folder.

Write into a temporary export directory, then publish completed outputs under `exports/<export_id>/`. Manifest includes source revision/content identity, run and selection, options, software versions, timing/units/basis, name mappings, gap actions and files. A stale request should require refreshing selection rather than silently exporting a newer run. Pin the open source snapshot for the job. Handle each requested format's success/failure clearly; never expose incomplete files as successful artifacts.

At the bottom of the mocap panel, add Secondary exports with Tall CSV, Wide CSV, NumPy, BVH, and glTF choices; show detailed options only for selected formats. Include Export now and Export after successful processing. Show selected recording/result and full recording versus selected time range. Default data exports to tall CSV, and distinguish raw keypoints, filtered keypoints, landmarks, and segment transforms in selection. Reuse controls in the setup modal's existing Exports section. Keep the existing `.blend` action separately identified during migration.

## Implementation order and completion checks

1. **Evidence spike:** read one saved calibrated recording, hydrate its saved definitions, calculate parent-relative translations and fixed-offset FK errors; prototype a short BVH and bone-only glTF. Import both into Blender. Deliver a numeric parity report and screenshots before choosing the default motion profile.
2. **Recording export foundation:** coherent snapshot selection, capability validation, artifact manifest, tall CSV and NPZ; then wide csv/NPY. Round-trip values, timestamps, names, nulls and units. Exercise multiple clocks, missing data, and static fit values.
3. **Shared motion preparation and BVH:** offset/rest-frame mapping, target conventions, resampling and gaps. Verify asymmetric poses, branching joints, moving roots, near-180-degree rotations and incomplete parents using independent FK/import results.
4. **glTF scene:** consume the same prepared motion, implement the shared bone recipe and points. Run a glTF validator and compare Blender-imported world transforms and bounds, then visually compare representative frames against playback. Extend to trails and other layers after this passes.
5. **Jobs/API/UI:** integrate export-now and after-processing, progress, cancellation, partial failure, stale revisions, artifact download/reveal and format-specific readiness. Verify export failure leaves the canonical recording usable.

Rough effort, not a commitment: the data writers are small; trustworthy hierarchy conversion and Blender equivalence are several focused iterations; scene-layer parity and polished job/UI integration add further work. Calendar estimates should follow the evidence spike rather than assume fixed-offset compatibility.

## Decisions for discussion

1. First success criterion: visual playback parity, editable conventional rig, or both together?
2. If fixed-offset FK differs from stored origins, should the default preserve recorded motion with translation channels, or produce a fitted animation rig with quantified residuals?
3. Is GLB the default packaging, with `.gltf` available alongside it?
4. Wide CSV: scoped files with readable headers plus a dictionary, or a single fully qualified table?
5. Which glTF layers are required initially, and does trajectory mean full paths or sliding trails?

Blender exposes BVH rotation order and root-only translation options, supporting the need to make that profile explicit: [Blender BVH export API](https://docs.blender.org/api/5.2/bpy.ops.export_anim.html). Actual interchange behavior still requires the import checks above.


### 2026-10-10 � student guides and V1 explorer restoration

- Located the notebook generator/template in local V1.8.2 and its separate
  NPY-to-Pandas example. V2 adds an optional Notebook Explorer format in the
  existing scientific export selection (saved-result and after-processing paths).
- Generated notebook uses relative Parquet access, a source-hash guard, selected
  run/data, explicit point/component order, Pandas, NumPy and Matplotlib. It
  does not install packages, change recording data, or archive the source Parquet.
- Static student tutorials are staged into exports/README.md and selected
  csv/README.md and npy/README.md. Existing tutorials are preserved. Examples
  cover provenance, shapes, missing data, metadata and Matplotlib plotting.
- Focused unittest checks pass for publication, retained/default paths, guide
  preservation and execution of NPY/NPZ examples. Notebook execution test is
  skipped because the core environment lacks pandas; generation/code compilation
  passes. UI TypeScript checking passes. Interactive notebook/app review remains.
- Log follow-up: export previews currently turn absent Parquet into a 404/error
  before processing. Separate actual failure involved a missing calibration TOML.
  Latest successful run took 598 s, including about 199 s across checkpoint writes,
  143 s detection and 106 s reconstruction; overlapping worker timings must not
  be summed. Handle absent-result UI state next, then profile these hotspots.
