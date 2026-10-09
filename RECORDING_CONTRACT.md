# Recording contract

Maintained target, version 1 (independent of the Parquet descriptor schema version).
This is the starting point for changes to recording
paths, saved settings, result retention and exports. It governs new implementation;
it does not claim that every existing writer has been migrated. The
[implementation audit](current-work-plans/03-transport/recording-folder-contract.md)
tracks those gaps. Update this contract and its validation together when changing
behavior. Preserve existing recordings and unknown historical metadata.

## Paths

The recording folder name is `recording_id` (`recording_name` in existing APIs).
Preserve the capture UUID separately when available. Paths within metadata should
be recording-relative where possible; original absolute input paths are provenance,
not required lookup paths after a recording is moved.

```text
<recording-id>/
    <recording-id>_recording_info.json  # capture metadata, when available
    <recording-id>_calibration.toml    # calibration convenience/input artifact
    <recording-id>_data.parquet        # all retained scientific runs
    videos/
        synchronized/                # original synchronized media; optional audio
            timestamps/              # capture timing sidecars, when available
                camera_timestamps/
        annotated/                   # derived videos, when requested
    output/
        diagnostics.yaml             # regenerated health report
    logs/                            # processing attempt logs, when generated
    exports/                         # created only when exporting
        <recording-id>.tall.csv
        <recording-id>.static.tall.csv
        <recording-id>.landmarks.wide.csv
        <recording-id>.npz
        <recording-id>.metadata.json
        run-0/                       # explicit retained export
            <recording-id>.run-0.tall.csv
            <recording-id>.run-0.static.tall.csv
            <recording-id>.run-0.npz
            <recording-id>.run-0.metadata.json
```

The tree is a location contract, not a requirement that every recording contain
every file. Imported videos may have no original capture JSON/timing. Unprocessed
recordings have no Parquet. Capability checks validate prerequisites for the
requested operation rather than rejecting every partial recording.

`RecordingStructure` owns backend path construction. Frontend structures/presets
must agree with the [machine-readable path cases](shared/recording-contract/paths.json).
Those cases are checked against both implementations. Read-only path construction
and inventory must not create directories. Optional export directories are lazy.

Existing `.blend` output at the recording root remains a compatibility location
until the Blender integration stage explicitly changes its writer/readers.
`charuco_board_info.json` is an optional calibration input. Existing observation
caches such as `output_data/charuco_observations_realtime.pkl` are disposable derived
artifacts, not canonical measurements; relocating them requires updating both
their readers and writers. `.processing.lock` and publication scratch files are
operational state, not user results.

## Ownership and sources of truth

| Information | Authority | Owner |
| --- | --- | --- |
| Capture identity, camera settings, media/timing associations | Capture recording-info JSON and original sidecars | SkellyCam; FreeMoCap reads/adapts |
| Processed samples, scientific definitions, retained runs, stage provenance | Embedded descriptor and rows in the recording Parquet | FreeMoCap recording package |
| Calibration solution | Calibration TOML; actual geometry used is frozen into each consuming run | FreeMoCap calibration |
| Default settings for a future operation | Application/package configuration | Relevant processing component |
| Settings actually used for saved output | That output's saved stage provenance | FreeMoCap publication |
| Exported artifacts and their freshness | Export metadata with per-artifact source revision and hash | FreeMoCap exports |

Capture metadata, processing provenance and export metadata have different scopes.
Processing never replaces capture settings with mocap options. User preferences
are defaults for future requests, not evidence about an existing recording.
Parquet is self-describing; a recording-info JSON mirror is not required to read it.


## Compatibility and writer migration

Current compatibility inputs include `synchronized_videos/`, `annotated_videos/`,
`<id>_info.json`, `<id>_camera_calibration.toml`, and older `output_data/` results.
Real recordings can mix layouts. Resolve each artifact from explicit associations
or known supported locations, not by declaring an entire folder legacy because
one old file exists. Never select an arbitrary first matching Parquet or TOML.
If multiple candidates are ambiguous, report them and require explicit selection.

Existing readers only partially implement this target. Preserve their behavior
until focused compatibility tests accompany replacement. Do not rename, move or
delete user recordings as a side effect of reading, processing or exporting.
Capture-writer changes belong to a separate SkellyCam stage with a human-owned
commit/push handoff. FreeMoCap must continue accepting installed capture output.

## Runs, revisions and attempts

- One Parquet stores all retained runs. Its descriptor contains `runs` and
  `selected_run_id`; every numerical row includes `run_id`.
- A run is a retained result slot. An overwrite updates that slot; keep allocates
  a new ID and retains the base. A kept result is independently readable, including
  reused input rows and scientific definitions. No dependency on a mutable base.
- A revision identifies particular published content. A run ID alone does not
  identify immutable content. Export retention binds both the ID and revision.
- An attempt is an execution that may fail or be cancelled. It does not become
  a new run merely because it started. Failed attempts do not claim completion.
- Completion and settings are published with their numerical outputs, under the
  existing recording lock and atomic Parquet replacement. Downstream invalidation
  removes its completion/provenance with its stale channels.
- Run selection chooses a view; it does not rewrite capture/calibration inputs or
  make old exports fresh. Keeping runs does not automatically retain side videos.

## Saving settings

Versioned typed provenance is stored in
`runs[run_id].processing[sensor_group].stage_provenance`. Its version is 1;
the outer Parquet descriptor stays at schema 1 for installed reader compatibility.
Use existing models, fits, camera
geometry and filtering reports as their authoritative values;
provenance references them instead of creating competing copies.

Each published stage's provenance is scoped to its actual group/source outputs
and contains:

| Field concept | Meaning |
| --- | --- |
| Effective settings | Complete resolved stage settings, including default-valued fields |
| Defaults baseline | The applicable defaults at execution, with schema/algorithm identity |
| Submitted request | Original request where useful, distinct from resolved settings |
| Input identity | Content/checkpoint fingerprints and referenced scientific definitions |
| Software identity | Actual package/algorithm versions and relevant model/native code identities |
| Execution/publication identity | UTC time, attempt identity and base run/revision where applicable |
| Output binding | Stage, sensor group and produced sources/channels/checkpoint |

Differences from defaults are derived from that saved baseline. A changed value
does not prove a human deliberately edited it: a preset or automatic resolution
may have supplied it. Do not claim user-edit attribution without explicit evidence.
Export checkboxes, Blender paths and UI preferences are not scientific stage
settings. Persist them in request/export provenance at their own scope.

For example, after a filter-only restart:

```text
run 0:
    observations: original tracker settings and original input/software identity
    filtering:    cutoff=4 Hz, execution-time default cutoff=6 Hz, new input binding
    reconstruction: new output/provenance consuming the 4 Hz filtered points
```

Never replace the observations' provenance with the new request. Never present
the old tracker source's whole mocap config as the effective settings of the new
filtering result. Keep copies upstream provenance; overwrite replaces only the
executed/invalidated scope. Store run lineage when allocating a new run.

Historical recordings may have only the existing tracker config, filter report,
model/scale-fit snapshots and calibration metadata. Read these faithfully and mark coverage
partial/unknown. Do not manufacture historical defaults, timestamps or versions.
The extension is optional for historical files and validated when present.
There is no silent rewrite of existing recordings on read.

Current coverage includes observations, timing, triangulation, filtering, scale,
reconstruction and biomechanics. Numerical restarts bind the base run
and descriptor fingerprint. Input fingerprints identify saved scientific inputs;
they do not yet provide a complete raw-video/model-weight dependency manifest.
Tracker provider settings describe the request: actual runtime provider fallback
is not exposed by the current adapter and is recorded as a limitation. Defaults
are execution-time application defaults, not proof of a user's choices. Complete
calibration-operation provenance and application-level run retention remain work
to do. The original tracker request remains available in the tracker source.

Calibration needs the same distinction: geometry used is already saved per run,
but the complete calibration operation's settings/provenance are separate from
that geometry. Bind the consumed calibration snapshot by identity, retaining its
available solver/board/alignment metadata without depending on an old absolute path.

## Export retention and publication

Normal export writes selected formats directly under `exports/`, replacing their
previous default files. Unselected files retain their original provenance.
Explicit retention writes `exports/run-<id>/` with run-qualified filenames and
must not silently clobber existing retained outputs. Additions to a retained set
must use the same bound revision; otherwise report a conflict.

Export metadata contains format/axis descriptions, source descriptor snapshots,
per-artifact revision/hash and status. NPZ embeds its own descriptions. A new NPZ
must not cause an old CSV to be described as current. Exporting does not allocate
a processing run or modify Parquet. Retaining exports alone does not retain a
historical scientific Parquet revision.

Use owned staging and an export publication lock. Individual replacements can be
atomic; a multi-file set is not a single filesystem transaction. Metadata and
hashes must make incomplete publication detectable. Preserve successful formats
when another fails; report export errors separately from numerical processing
success. Overall run success also requires validation of every required output,
as defined below.
Detailed format rules live in the [export plan](current-work-plans/02-pipeline/secondary-exports.md).

## Reproducible validation and implementation status

From the FreeMoCap root, using the already installed development environment:

```powershell
.\.venv\Scripts\python.exe -B -m pytest freemocap/tests/test_recording_folder_contract.py -q -p no:cacheprovider
```

The contract tests compare Python paths to frontend YAML and the shared examples,
and check lazy export paths, capture preservation and the hybrid-layout inventory
behavior currently supported. They do not certify all legacy resolution or settings
persistence. Temporary outputs use pytest's external temporary directory; a caller
can supply an ignored `--basetemp` for local reports.

| Area | Status |
| --- | --- |
| Canonical path examples, cross-language drift checks, lazy exports path | Implemented with this contract |
| Embedded runs, scientific snapshots, keep/overwrite storage primitives | Existing implementation |
| Versioned stage provenance and saved defaults | Implemented for posthoc publication and saved-stage replay; coverage limitations above |
| Consistent app keep/overwrite and run lineage | Pending |
| Canonical capture/calibration writer migration and complete hybrid resolution | Pending staged work |
| Tall CSV, metadata, retained exports and interrupted publication recovery | Backend/CLI implemented; verified on test/sample Parquet |
| Wide CSV, NPZ and posthoc Exports controls | Pending export stages |
| Retained annotated videos and Blender adaptation | Follow-up |

For every settings change validate: full processing; changed-filter restart with
unchanged detector provenance; keep/overwrite; failed publication; unknown legacy
provenance; and reload without consulting current defaults. For every path change
validate: canonical, legacy and mixed inputs; ambiguity; missing optional artifacts;
and a moved recording. Keep current-state audit notes out of the normative rules.

### Real recordings are the acceptance boundary

Use the existing [dataset workflow](freemocap/tools/datasets/README.md) and its
test/sample recordings as the common producer for contract and export acceptance.
Do not create a second preparation pipeline or replace production processing with
mocked arrays in the acceptance suite. Small structural/logic tests remain the
fast check for invariants and failure handling; they do not certify integration.

For changes to saved data or processing, run fresh processing in an isolated
prepared root, then reload and reprocess its actual Parquet files. Check the
existing ready marker, hashes, frame grids, stage settings and scientific output
validation. Preserve original recordings and accepted prepared results. A missing
dataset or unavailable native dependency is an explicit skip/blocker, never a pass.

The short recording (222 frames, 6 Hz) is the quick integration case; the sample
recording (1,108 frames, 30 Hz) is the full acceptance case. Their differing filter
defaults are intentional. Test both optional-fit paths, preserving upstream
measurements and provenance during numerical replay and cancellation.

As CSV/NPZ writers land, extend these consumers to compare exported values,
missing-data masks, frame/entity ordering, units and axis descriptions against the
same verified Parquet. Exercise default replacement, retained-run exports and
partial failure with these outputs. Blender becomes another consumer of this
fixture chain. Scientific comparisons use appropriate numerical tolerances;
file hashes bind a particular artifact, not a promise of bitwise deterministic
GPU results across fresh runs. Dataset validation is an integration benchmark,
not proof of anatomical accuracy.

### Complete-run output acceptance — owner requirement, 2026-10-09

A standard reference run includes the saved Blender scene as well as canonical
Parquet. Numerical completion is a reusable checkpoint; overall run success
requires every output declared by the run's acceptance profile to be generated
and independently validated. Preserve successful numerical results when an export
fails, but report the overall run as incomplete or failed. A missing dependency,
skipped required check, cancellation, or unsupported required format cannot pass
the complete-run gate. Explicit calibration-only and numerical-only checks remain
useful, with their narrower scope visible in results.

The reference acceptance profiles must exercise wide CSV, NPY and NPZ as those
writers land. These are independently selectable outputs in ordinary runs;
overall success requires the outputs selected for that run. Every
additional requested output must also pass its format checks. Tall CSV remains
an explicitly selected export; direct FBX/BVH remain deferred. Blender-mediated
FBX/BVH acceptance is required when those outputs are requested and supported.
An unsupported requested output must fail preflight rather than disappear from
the required set. Record the profile version and required outputs before execution
so a failed writer cannot silently reduce the definition of success.

Each artifact report binds its recording/run, group/source selection, source
Parquet revision and hash, effective export options, relative output path, file
hash, validator version, and validation outcome. Blender reports also identify
the Blender runtime and add-on build. File existence and hashes establish artifact
identity; consumer checks establish content validity:

- Parquet: existing frame/channel coverage, scientific geometry and provenance checks.
- Blender: reopen the produced `.blend` in a fresh Blender process; verify the
  selected recording and run, expected scene/model structure, frame/time mapping,
  units and coordinate conversion, and evaluated point/segment transforms against
  the same Parquet. Cover missing samples and saved-segment motion across the
  recording. Constraint/cleanup routes need their own declared transformation
  expectations and tolerances; they cannot inherit exact saved-segment equivalence.
- Wide CSV and NumPy (NPY/NPZ): reload written files and compare values, names, ordering,
  frames/timestamps, units, components and missingness with the source snapshot.
  Verify static outputs, NPY companion arrays/manifest, NPZ's standalone metadata,
  and pickle-free loading. Resolve each format's channel selection against the
  same source snapshot and validate exactly that declared selection.
- FBX/BVH: reimport the written artifact and check hierarchy, motion, timing,
  scale, axes and any declared approximation against the selected Blender route.

Publish a complete-run `ready.json` only after all required checks pass. Reuse and
`validate` must verify the required-output profile, source binding and every
artifact hash; legacy Parquet-only markers do not certify complete-run acceptance.
Changed numerical results invalidate dependent exports, including after saved-stage
reprocessing or reconstruction-refresh helpers. Export retry may reuse successful
numerical results without detection or reconstruction. A failed candidate must
preserve the previously accepted preparation. Consumers must use the common
readiness check instead of interpreting mocap task status alone as acceptance.

The dataset producer now defaults to the versioned `standard` profile: Parquet
and a native-segment Blender scene. It preflights Blender, reopens the saved scene
in a separate process, checks every recorded frame, and publishes readiness only
after both artifacts pass. `--output-profile numerical` explicitly selects the
narrower checkpoint. `datasets export` upgrades old preparations or retries a
failed Blender output on an isolated copy without rerunning numerical processing.
The common readiness check verifies artifact hashes and source/run bindings;
reconstruction refresh invalidates the complete-output report.

General application export-job status and CSV/NPY/NPZ acceptance remain subsequent
stages. Extend this gate with each writer as it lands; do not defer that writer's
validation to a later milestone.

## Trajectory products

Reconstruction stores `anchor_segment_name` with the recorded model. Placement walks
the connected measured component from that segment in either direction; anatomical
parents, local-rotation conventions and joint-angle definitions remain unchanged.
The anchor does not affect scale evidence, so changing it can reuse a saved scale fit
while invalidating reconstruction and dependent outputs. Live anchor changes preserve
the current scale windows and roll history. Missing anchor observations produce no
connected geometry; missing intermediate poses still break the chain.

Live dimensions are refitted every frame from up to 30 valid readings per segment
by default, using medians and shrinkage toward a pooled model scale. This is not a
fixed-duration window when observations are intermittent, and absent segments retain
their previous readings. There is no hard per-frame bound on length changes. Post hoc
fits dimensions over the recording and holds those dimensions fixed during reconstruction.

- `RAW_KEYPOINTS_3D` and `KEYPOINTS_3D` retain tracker identities and raw/filtered provenance.
- `MAPPED_KEYPOINTS_3D` retains mapping observations keyed by canonical model landmark names.
  Its model source identifies the tracker; `RecordedModel.mappings` stores the mapping definitions.
- `LANDMARKS_3D` contains model-local landmarks scaled by the fitted segment scale, rotated
  by the owning segment orientation and translated by its solved origin. It is produced
  whether or not center of mass computation is enabled.
- `SEGMENT_ORIGINS` stores translations keyed by segment and paired with `ROTATIONS_WORLD`.
  Forward kinematics anchors the root at its measured origin and places each child at
  its parent's scaled, rotated `connect_at` landmark, preserving measured orientations.
  Scale fitting and roll estimation use observations before this connection step.

Mapped observations survive frames without solvable poses. Landmarks require both the
owning pose, every ancestor pose through the observed root, and a fitted scale;
absent results remain missing, with no observation or
unit-scale substitution. Each product retains its run, source, sensor group, reference
frame, units and sample grid. Both model point channels belong to reconstruction and are
invalidated together. Connected optimization is deferred to `development-skelly-fit`;
there are no connected-solver sources or stages in the streaming contract.

Live view and recording playback show original keypoints, mapped keypoints (cyan), and
landmarks as independently selectable layers. Playback uses recorded definitions.
This is the single supported contract. Older mixed landmark recordings are unsupported;
there is no compatibility reader, semantic version field, or automatic migration.
