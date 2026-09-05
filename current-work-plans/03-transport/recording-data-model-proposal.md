# Recording data model

Status: agreed implementation direction, 2026-09-05. Concrete implementation choices below are
specified for the posthoc rebuild; exporter container mechanics remain a later phase.
See [posthoc rebuild](../02-pipeline/posthoc-rebuild.md).

## Recording layout and identity

The folder name is recording_id. All paths come from RecordingStructure.

```text
<recording_id>/
  <recording_id>_recording_info.json
  <recording_id>_data.parquet
  <recording_id>_calibration.toml       # selected result's calibration, when available
  videos/
    synchronized/
    annotated/                       # when generated
  output/                            # requested additional exports
  logs/                              # this recording's processing logs
  <recording_id>.blend                # optional export
  <recording_id>.run-0.freemocap.mp4   # default annotated grid + embedded data
```

Existing capture timestamp files remain inputs. The processed data includes the timing needed to
interpret it; there is no separate timing Parquet. Reconcile the existing recording_name path field
with recording_id without generating another identity. An existing SkellyCam recording_uuid may be
preserved as metadata; it does not replace the folder's recording_id.

One Parquet holds the explicitly retained runs. Default run_id=0. Reprocessing may overwrite the
selected run or keep it and create a new integer run_id. There is no automatic history directory.

## The shared model is the starting point

SkellyForge supplies SkeletonDefinition, AnatomicalLandmark, RigidBodySegment, RestPose,
JointDefinition/EulerConvention, SkeletonPose/SegmentPose and coordinate conventions.
FreeMoCap's FrameMessage carries models, instances, trackers and ChannelBlocks.

Disk flattens those channels:
- ChannelBlock.kind -> channel.
- Model-indexed names or inline names -> name.
- ChannelBlock.columns -> component.
- Numeric array entries -> value.
- The enclosing tracker or instance -> source.
- Camera/coordinate context -> reference_frame.
- Capture sampling sequence -> sensor_group and frame_number.

The render-oriented ModelDefinition omits scientific details such as anatomical definitions and
joint conventions. Its disk descriptor also preserves the resolved SkellyForge definitions required
to interpret the result. Do not reconstruct scientific structure from installed defaults or names.

Source files:
- ../../../skellyforge/skellyforge/core/skeleton/skeleton_definition.py
- ../../../skellyforge/skellyforge/core/skeleton/components/anatomical_landmark.py
- ../../../skellyforge/skellyforge/core/skeleton/linkage/joint_definition.py
- ../../../skellyforge/skellyforge/core/skeleton/skeleton_pose.py
- ../../freemocap/core/streaming/message_model.py
- ../../freemocap/core/streaming/message_composer.py
- ../../freemocap/core/streaming/producers/

## Numeric schema

```text
timestamp_s, sensor_group, frame_number, source, reference_frame,
channel, name, component, value, units, run_id
```

| Column | Type | Meaning |
|---|---|---|
| timestamp_s | float64 | Capture/sample time on the shared recording clock, relative seconds |
| sensor_group | string | Sampling sequence, e.g. a synchronized camera group or eye tracker |
| frame_number | int64 | Sample number within that sensor group's sequence |
| source | string | Existing tracker, instance, or timing source described in metadata |
| reference_frame | string, nullable | Spatial frame; null for reference-independent scalars |
| channel | string | Registered ChannelKind/output type |
| name | string | Model landmark, segment, joint or channel-defined name |
| component | string | x/y/z, w/x/y/z, visibility, named angle, scalar component, etc. |
| value | float64, nullable | Numeric component; null for missing data |
| units | string | Per-component units: mm, px, rad, s, 1, etc. |
| run_id | int64 | Nonnegative retained processing result number; default 0 |

Recording identity is metadata, not a repeated row column. Analysis combining recordings may add it.
The component key within a recording is:
(run_id, sensor_group, frame_number, source, reference_frame, channel, name, component).
Matching null reference frames count as duplicates. Units and timestamps are validated properties,
not extra dimensions allowing duplicate measurements.

## Time first; sample numbers are local

Timestamp is the primary temporal coordinate for comparison/playback across systems. Frame numbers
identify samples within a sensor group; there is no recording-wide frame sequence.

| timestamp_s | sensor_group | frame_number |
|---:|---|---:|
| 1.000000 | mocap | 30 |
| 1.000000 | eye_tracker | 120 |
| 1.008333 | eye_tracker | 121 |
| 1.016667 | eye_tracker | 122 |
| 1.025000 | eye_tracker | 123 |
| 1.033333 | mocap | 31 |
| 1.033333 | eye_tracker | 124 |

These are idealized examples. Preserve actual sample times and do not upsample/downsample on storage.
Alignment uses timestamps and a declared interpolation/nearest-sample policy with a maximum gap.
Do not equate frame numbers across groups or assume exact timestamp equality across devices.

recording_info describes each group's sample numbering, clock mapping, offset/drift correction and
synchronization method/accuracy. Derivatives use actual time differences. Unknown capture timing is
reported explicitly; nominal video timing for imports must be identified as estimated video timing.
First implementation consumes current camera recordings; mixed-rate fixtures enforce the schema
without pretending a new eye-tracker acquisition integration already exists.

A camera-scoped observation can have its own capture timestamp within the group's synchronized frame.
For given run/group/frame/source/reference context, sample timestamps are consistent. Fused mocap
results use that group's synchronized timestamp. This is a convention of the output channel, not
permission to replace the original camera capture times.

Add TIMESTAMPS as a registered channel in the same table. Group timing uses source=the group's
declared timing source, name=synchronized, component=timestamp_s, units=s, reference_frame=null.
Emit it for every group sample even when no detector succeeds. Per-camera timing uses its declared
camera timing source and name=capture. The metadata maps these sources to groups/cameras explicitly.
There is no universal "recording frame" timing source across independent groups.

## Sampling, ownership and coordinates are separate

- sensor_group answers: which sample sequence does frame_number belong to?
- source answers: whose output is this (tracker or reconstructed instance)?
- reference_frame answers: in which coordinates is it expressed?

A human and a board may share the mocap group. World-space gaze can belong to a 120 Hz eye-tracker
group. Therefore these three columns cannot substitute for one another.

| source | channel | reference_frame | Meaning |
|---|---|---|---|
| rtmpose | OVERLAY_2D | camera_a_image | Detector keypoints in camera A's image |
| rtmpose | KEYPOINTS_3D | world | Tracker-named 3D points |
| human | LANDMARKS_3D | world | Reconstructed instance landmarks |
| human | OVERLAY_REPROJECTIONS | camera_a_image | Instance segment origins projected into camera A |

Source labels are opaque references to existing tracker/instance descriptors, never parseable
combinations like pose_camera_a. Those descriptors retain model and instance identities. Two
instances get distinct sources. Camera frame descriptors reference the actual camera, image rotation,
dimensions and projection convention. A reference frame does not claim which cameras contributed
to fused data.

Parent-relative rotations reference the actual parent segment frame, resolved from the instance and
skeleton topology. No ambiguous bare "local"; root orientation explicitly references world.
Length/confidence scalars have null reference_frame. Channel kind and reference frame must agree.

## Channels and scientific semantics

| Channel | Names | Components / units |
|---|---|---|
| KEYPOINTS_3D | tracker keypoints | x/y/z: spatial units; reprojection_error: px if computed |
| LANDMARKS_3D | model landmarks | x/y/z: spatial units; quality only if computed |
| SEGMENT_ORIGINS | model segments | x/y/z: spatial units |
| ROTATIONS_WORLD | model segments | w/x/y/z: 1 |
| ROTATIONS_LOCAL | model segments | w/x/y/z: 1 |
| SEGMENT_LENGTHS | model segments | length_mm: mm for the current metric convention |
| DERIVED_POINTS | named derived points | x/y/z: spatial units |
| JOINT_ANGLES | model joints | convention.angle_names: rad |
| OVERLAY_2D | tracker keypoints | x/y: px; visibility: 1 |
| OVERLAY_REPROJECTIONS | model segments | x/y: px; quality only when meaningful/computed |
| TIMESTAMPS (addition) | capture/synchronized | timestamp_s: s |

Use existing kinds and definitions; channel distinguishes output type. There is no generic
per-row stage/provenance classification, and directly mapped/weighted/anatomically offset landmarks
all remain LANDMARKS_3D. Internal evidence masks may still be needed for correct fitting; they are
not a generic public provenance column.

Component metadata must declare units, including mixed-unit channels. Use SkellyForge's named joint
angles directly rather than the current producer's synthesized joint.angle_0 names. Use actual model
names, hierarchy and conventions. Preserve wxyz orientation semantics; missing parent orientation
cannot be replaced with world orientation under a parent-relative label.

Missing numeric values become null; never zeros, infinity or invented confidence. Enabled channels
declare names/components and expected coverage so missing measurements can be represented without
confusing them with uncomputed stages. Computation faults raise errors. Single-camera projection
must declare its actual frame/units; unscaled geometry cannot be labeled metric biomechanics.

Stage reprocessing requires distinct checkpoint outputs where two stages produce the same kind of
geometry. The rebuild plan defines limited additional channel kinds, not an arbitrary stage column.

## Metadata and constant channels

recording_info contains:
- Recording ID, capture start, inputs, camera configurations, sensor groups and clock definitions.
- Schema version and selected_run_id.
- Per retained run: command argv or API request, resolved settings, software versions, stage status,
  dependencies, timing/quality statistics, exact calibration used, and computed output inventory.
- Per-run model/instance/tracker/source/reference-frame descriptors, including resolved scientific
  definitions, so retained results never inherit another run's model settings.
- Component/unit contracts, static/dynamic channel declarations, and fitted instance measurements.
- Export status and selected run/options when exports exist.

Store globally fitted posthoc scale/segment lengths/scales once per run/instance as static channels.
Readers broadcast them when reconstructing samples. Never maintain independent static and repeated
dynamic versions of the same channel.

Implementation status: the complete SkellyForge fit is stored once in each run's typed `scale_fits`
records, bound to sensor group, source, reference frame and spatial units. An explicit null fit means
no scale evidence was available. Static channel views of fitted scale/segment lengths/scales remain
to be exposed from that record; they must be derived views, not a second authoritative measurement.
Stage invalidation and keep/overwrite include these fit records.

Embed the numeric dataset's interpretation descriptor, including retained runs, in Parquet metadata.
The JSON document carries the same descriptor plus mutable operational/log/export information.
Generate shared fields from one model. The completed Parquet is authoritative for its embedded
dataset descriptor; the reader validates matching JSON fields and reports/reconciles interrupted
publication rather than combining mismatched descriptions.

## Keep and overwrite

Default run_id=0. Overwrite targets the selected existing run. Keep allocates max(existing run_id)+1
under a recording write lock and preserves the selected base run. Both retain unrelated runs.
Do not use an attempt counter or timestamp as run_id.

Keep produces a self-contained target result: copy reusable upstream channels/static metadata under
the new run_id and compute requested descendants. This deliberately avoids cross-run references.
Overwrite replaces the affected outputs and removes invalid descendants from that run; stale
biomechanics or exports must never appear current. Details are in the rebuild plan.

## Default recording video and optional exports

CSV(wide or tall), .NPY, BVH, .FBX, GLTF, .c3d, .xlsx and Blender are adapters over the canonical reader, never required to finish
mocap processing. Every exporter selects a run explicitly.

The default `<recording_id>.run-<run_id>.freemocap.mp4` contains:
- Synchronized video grid annotated using the shared UI overlay renderer. The optional raw grid is `<recording_id>.run-<run_id>.raw.freemocap.mp4`.
- Relevant recording/model information and the selected run's kinematic data.
- Grid tile/camera/variant layout and video presentation-time -> recording-time mapping.
- Versioned FreeMoCap payload identification and extractable data.

Preserve native data sample rates inside the payload regardless of grid-video frame rate.
Prefer embedding the same JSON/Parquet representation, not inventing another numeric schema.
Prototype an MP4 extension mechanism (such as a UUID box), extraction and player compatibility in
the export phase before fixing the binary protocol. MP4 timebase mapping, clipping and any grid
frame repetition are explicit. Suffix alone is not payload validation.
See https://mp4ra.org/ for MP4 extension mechanisms.

## Implementation checks

Round trip mixed-rate samples, multiple sources, camera/world/parent frames, named joint angles,
missing data, static fits and retained runs. Validate the schema before changing pipeline math.
Use typed bounded array/Arrow batches before wire float32 packing; do not route disk through CBOR.
Scientific computation belongs to SkellyForge, detection/mapping to SkellyTracker, and recording
assembly/orchestration to FreeMoCap.

Video retention, publication and stale-output handling follow [processing and playback integration](../02-pipeline/processing-and-playback-integration.md#recording-video-output).
