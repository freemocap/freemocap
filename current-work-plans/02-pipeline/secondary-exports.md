# Secondary recording exports

Status: investigation and proposal, 2026-09-22. No implementation or format decisions are approved by this document.

## Assessment

The current Parquet contract appears to contain the ingredients for data exports and animated scene exports. CSV/NumPy are comparatively straightforward. glTF visual playback is moderate work. A conventional BVH rig with demonstrated equivalence to playback is the highest-risk part: stored segment positions are not automatically the positions produced by a fixed-offset joint hierarchy.

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

- CSV/NumPy preserve original timestamps. BVH needs an explicit uniform FPS and pose resampling. glTF can retain original times when exported alone; paired exports share the BVH grid.
- Normalize animation time to zero and preserve original start time in the manifest. Do not infer timing solely from nominal video FPS when saved timestamps exist.
- Use linear position interpolation and quaternion-aware orientation interpolation with sign continuity. Never interpolate Euler channels as the primary resampling representation.
- CSV/NumPy preserve missing values. Animation export requires a declared policy: strict complete interval, split valid intervals, bounded interpolation, or explicit holding. Never synthesize identity rotations or origin positions silently. Hierarchy validity includes required ancestors.
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
2. **Recording export foundation:** coherent snapshot selection, capability validation, artifact manifest, tall CSV and NPZ; then wide CSV/NPY. Round-trip values, timestamps, names, nulls and units. Exercise multiple clocks, missing data, and static fit values.
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
