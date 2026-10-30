# Runtime tensors, recording storage, and exports

## Approved implementation decisions — 2026-10-28

This section supersedes conflicting terminology and proposals in the earlier
design discussion below. Generic storage is `DataTensor`; data with an explicit
sample-axis/timeline binding is `TimeSeries`. Neither name asserts empirical
measurement. Dimensions derive from declared axis identifiers, not fixed coordinate
counts or a mandatory rank. Live and post-hoc use the same authored entity and
declared component ordering. Instance identity is a nonnegative integer defaulting
to zero. Current timestamp production stays unchanged; this task does not redesign
clocks, resampling, transport timing or compatibility modes.

`freemocap/core/data_tensors/` implements `AxisDefinition`, `SourceIdentity`,
`TensorLayout`, `AxisSelection`, `SampleTimeline`, `CompanionTensor`, `DataTensor`,
`TimeSeries` and `RecordingDataset`. Selections are bound to their complete
declared layout; contiguous selections expose views, while other selections
gather into a new array.

`DataTensor` initially borrows numerical arrays. `immutable_copy()` publishes
independent, protected values and companion arrays; `mutable_copy()` makes an
independent writable result. Already published tensors are reused. `TimeSeries`
binds one declared sample axis to the existing IDs and timestamps, regardless of
that axis's position. `frame_view()` retains a length-one sample axis;
`slice_samples()` retains the original sample identities and timestamps. These
views share numerical storage without rescanning values or recomputing timing.

Presence and validity use the full value layout. Confidence, measured support
and solver status may use explicitly matching subset axes. Their numeric dtypes
are checked; valid entries must be present when presence is supplied and must
contain finite values. Scientific provenance is explicit and does not classify
every numerical output as an empirical measurement.

`RecordingDataset` holds already published time series and static tensors by
reference. It rejects ambiguous channel identities and conflicting definitions
of the same timeline ID. Different camera or sensor timelines remain independent;
assembly does not resample, concatenate or repeat static fits across frames.
Model/reference definitions can be retained once as immutable `DefinitionDocument`
JSON metadata. A dataset contains one selected range per channel; bounded
publication and saved-stage migration remain subsequent pipeline work.

Recording channels expose the common layout, and `ChannelSeries` validates actual
sample identifiers and array shape/dtype before serialization. Streaming channels
expose matching entity/component axes with explicit Float32 precision; their layout
adapter checks byte counts when entity IDs are supplied. Live joint outputs now
follow authored order, including unavailable declared joints. The old dictionary
packing helper and remaining producers still require migration in subsequent
pipeline work; this foundation does not claim to remove all truncation/boxing paths.

`SeriesSampling` shares validated numerical timing across a recording publication.
`ChannelArrays.to_data_tensor()` and `.to_time_series()` borrow the saved reader's
arrays while checking declared identities and exact timing. Borrowed memory maps
remain valid only inside `ordered_arrays`; publish an immutable copy before leaving
that context. Existing saved visibility columns retain their meaning and order;
the adapter does not silently reinterpret them as a new companion channel.

Validation uses unittest in the existing core environment, plus the production
`datasets process test_data --output-profile numerical` workflow. The isolated
2026-10-28 reference output is at `C:/tmp/fmc-tensor-1028`; its processing attempt
is `freemocap_test_data/attempts/dc984bb3`. All 222 frames from three cameras were
processed with the graph pipeline. The numerical output profile does not include
Blender complete-run acceptance. Reference consumer tests use
`FREEMOCAP_PROVENANCE_PREPARED_ROOT` and verify that the input Parquet is unchanged.
Tests cover memory-map closure, independent timelines, static fits and saved model
definitions as well as shape, dtype, identity and ownership failures.

With owner approval, pytest 9.1.1 (the existing lockfile version) was installed
into core's `.venv` for the reference processing tests. `pyproject.toml` and
`uv.lock` are unchanged. No timestamp-generation, on-disk format or frontend
migration is included in these interface changes.

The reference replay also exposed an existing checkpoint guard mismatch:
`RecordingFitInputs` excludes `anchor_segment_name` from fitted-scale identity,
but publication required complete model equality even when only the fit was
retained. The guard now uses the existing fit-definition comparison in that case.
Retained dynamic or static model channels still require complete model equality,
including channels belonging to an unselected sensor group.

Final verification: 89 focused tensor/recording/message checks passed through
unittest, and the full 222-frame live replay passed separately. The pytest run
passed 95 checks and exposed the checkpoint issue above. After its repair, all
20 focused checkpoint and saved-stage tests passed, including the previously
failing real test-data replay; sample_data was deliberately deselected. Logs are
in `.test-artifacts/tensor-contract/{unit-tests,replay,pytest,checkpoint-tests}.log`.
Live replay checked worker/shared-memory cleanup and preserved the source
Parquet. It used CUDA fallback because TensorRT libraries were unavailable and
reported poor camera-matching fitness under the existing continue policy; these
are correctness checks, not reconstruction-accuracy or throughput acceptance.

## Tracking and reconstruction completion — 2026-10-29

Global 2 is implemented and reference-tested. Core now uses Forge's `PoseTensor`,
numerical roll resolution and joint calculations for recording and live results.
`recording_roll_adapter.py` is removed; immediate streaming producers consume
array-backed channel views. Forge commit `0038076` groups compatible segment
recovery and prepares immutable geometry once, eliminating the measured live
reconstruction regression. The [compliance map](tensor-contract-audit.md) records
the tests, numerical comparisons, timing measurements and allocation limits.
The dated migration account below describes the earlier stage, not open work.
Global 3 addresses Parquet reading/publication; viewer trails are deferred.

## Earlier tracking and reconstruction migration — 2026-10-28

Global 2 has a validated core implementation, with the Forge dependency stage
still outstanding. `ObservationArrays` borrows existing Tracker arrays and shares
prepared identity selections across consumers. `ObservationBuffer` assembles
recordings with array operations instead of point-by-point assignments.

`ModelRecordingReconstruction.channel_tensors` replaces its per-frame results.
`RecordingPoseOutputs` consumes the existing Forge batch representation and
produces immutable numeric channels with presence and solver-status companions.
`ReconstructionRecording.series()` publishes those buffers directly. Sample axes
use recording positions until the publisher binds existing frame IDs/timestamps;
they do not manufacture a timeline. Scientific units/reference context stays at
the existing publication boundary. Live and recorded paths retain the same
quaternion, angle, scale-fit and temporal-roll conventions.

The remaining `recording_roll_adapter.py` converts arrays to Forge pose objects
only because `ContinuousRollResolver.resolve_pose` has no array interface.
Forge's joint calculations also still require object-dtype pose-solution metadata.
These dependency interfaces and the live result dictionaries must be migrated
before Global 2 is complete. That requires the human-owned repository handoff;
no dependency checkout or environment was changed during this core stage.

The [updated compliance map](tensor-contract-audit.md) records the fresh reference
processing, live/saved-stage tests, scientific-output comparison and limited
observation-assembly benchmark. This work does not change the Parquet/NPZ/CSV
formats or the frontend.

## Earlier design discussion

Status: proposed contract for review, 2026-10-28. No runtime or file-format
implementation is claimed. This extends the playback/Parquet audit to the full
processing pipeline. The existing RECORDING_CONTRACT.md remains authoritative
until implementation and migration explicitly update it.

## Responsibilities

- Parquet is the primary durable record of published scientific results and their
  interpretation/provenance. It is not the numerical working representation.
- Runtime scientific objects wrap dense numeric arrays with explicit axes,
  timelines, masks, units, and reference frames. Helpers operate on these arrays.
- NPY plus a manifest, or NPZ with an embedded manifest, serializes those same
  scientific tensor payloads. Loading recreates equivalent tensor-backed objects.
- Wide CSV is a spreadsheet projection, one compatible timeline per table.
  Tall CSV remains an optional existing interchange projection.
- Browser display buffers are derived representations. Float32 conversion,
  renderer ordering and GPU layout are explicit, cached adaptations; they do not
  redefine the scientific values saved in Parquet or NumPy exports.

Strict parity means the same numeric values, dtype, shape, axis identities,
missingness, timing, units and scientific meaning for the selected recording dataset.
It does not mean preserving Python class identity, caches, memory addresses,
arbitrary strides, or aliasing. No Python object arrays or pickle in exports.
NPZ is a packaged recording dataset, not the incremental runtime working store.

## Proposed memory objects

### Naming convention

Use meaningful two-word domain names consistently in prose and proposed APIs:
**measurement tensor**, **recording dataset**, **channel layout**, and **sample
timeline**. The recording dataset is an identified collection of measurement
tensors plus their companion tensors, static fits, definitions and provenance;
it need not occupy one contiguous allocation or contain every retained run.
Avoid generic standalone names for these concepts. Existing source identifiers
remain unchanged when cited. See [project naming guidance](../../CONTEXT.md#naming-guidance).

Names below describe responsibilities, not a requirement for identical classes
in independent repositories. F = samples in a measurement tensor; P = points; S = segments;
J = joints; D = components. Measurement tensors are bounded; F need not be a whole recording.

| Object | Data and responsibility |
| --- | --- |
| ClockDomain | Clock identity, time unit and origin/epoch description. Distinct clocks are not implicitly comparable. |
| SampleTimeline | Timeline ID, clock ID, ordered int64 sample IDs and float64 timestamps in seconds; timestamps finite and strictly increasing within a continuous epoch. IDs need not be consecutive. |
| ClockRelation | Explicit, versioned mapping between clock domains with provenance and applicable interval. Offset/drift mappings can be added without rewriting samples. Unknown relations stay unknown. |
| ChannelLayout | Stable ordered entity/component axes, component units, source, sensor group, reference frame and channel kind. Layout changes create new measurement_tensors/layout IDs. |
| MeasurementTensor | Numeric values normally [F,N,D], layout and timeline references, sample range and masks. Static values use [N,D] with no invented time dimension. |
| ObservationBatch | Image positions [F,P,2], confidence [F,P], availability and detector status per camera/source timeline. Boxes use numeric arrays and masks with explicit instance/stage axes. |
| PositionSeries | Positions [F,P,3], measurement support and relevant quality arrays; raw, filtered, mapped observations and model landmarks remain distinct products. |
| PoseBatch | Origins [F,S,3], world/local wxyz rotations [F,S,4], availability and numeric solution/status codes. Optional scales/residuals remain separate typed arrays. |
| ReconstructionBatch | Pose, landmark, joint-angle [F,J,D] and derived-point measurement tensors, with shared model definitions and static fits. Does not materialize one result object per sample. |
| RecordingDataset | Versioned inventory of measurement tensors, layouts, timelines, definitions and provenance for one identified recording dataset/run selection. Owns lifecycle, not an obligatory monolithic allocation. |
| DisplayBuffers | Derived typed-array buffers and compiled topology/layout bindings owned by the rendering path. |

Metadata registries may use maps. No per-point or per-scalar dictionaries on
numeric hot paths. Frame access returns array views with shared layout metadata;
it does not rebuild name indexes or individual point/segment objects.

## Timelines and clocks

A clock domain and a sample timeline are different. Two streams can use the same
clock but sample at different rates or lose different samples. Conversely, equal
frame numbers or equal nominal rates do not establish clock alignment. Sensor
group membership does not imply an identical timeline for every source.

Example: 30 Hz cameras and a 200 Hz IMU retain independent timelines and tensor
lengths. They export together without padding, truncation or resampling. A camera
group's synchronized timeline is an explicit derived timeline; original camera
capture timelines remain identifiable. Clock resets start a new epoch/timeline.

Operations requiring a common grid must declare it. Alignment/resampling produces
a new derived product with source references, interpolation/hold policy, maximum
gap/tolerance and provenance. Playback maps its presentation time into each known
source clock and samples according to a declared policy. An unaligned source must
not silently appear synchronized. A device nominal frequency is descriptive,
never a replacement for stored timestamps.

Share a timeline only when its identity and exact sample/time arrays agree.
Do not use approximate timestamp equality to deduplicate strict tensor exports.
Array positions are not global frame numbers. Chunk boundaries and sample ranges
must preserve this distinction.

## Layout, missingness and ownership

- Scientific coordinates retain float64; IDs use int64, masks bool and statuses
  explicit integer enums. Other sensor quantities declare their own numeric dtype.
  Conversion must be explicit, not blanket float64 coercion of arbitrary signals.
- Canonical owned payloads use documented sample-major ordering. Slices may be
  strided views; methods requiring contiguous data materialize once at a declared
  boundary. An arbitrary gather is not advertised as zero-copy.
- For floating channels, present=false means no recorded entry; present=true
  with NaN means recorded unavailable/null. Finite usable values require presence.
  Integer channels use a separate validity mask when nullable. Quality/confidence,
  measured-versus-inferred support and solver status are distinct from presence.
- Missing whole samples are represented by the timeline or an explicit dense grid
  and masks; they are not inferred from a nominal frequency. Never compress away
  missing entities in a way that changes column identities.
- Producers own mutable builders. Published measurement tensors are read-only by contract and
  expose no writable aliases. A frozen dataclass alone does not enforce this.
  Mutating algorithms request owned output/scratch explicitly. Views keep their
  owner alive; release is tied to consumer completion, including worker/GPU use.
- Precompile name-to-index selection and model topology. Keep numerical work in
  array kernels/GPU operations. Stateful temporal algorithms preserve ordered
  dependencies using numeric state, including resets and chunk carry-over.
- Do not replace loops with map/comprehension syntax and call it vectorization.
  Loops over bounded measurement tensors, layouts, model topology or heterogeneous solver groups
  are permitted; repeated scalar boxing and per-frame metadata rebuilding are not.

## Persistence and export parity

Both live in-memory and Parquet-backed adapters expose the same logical tensor
selection contract. Parquet projection/pruning and reconstruction of validated
measurement tensors belong in one core reader module, not each consumer. Writer adapters emit
Arrow columns directly from measurement tensors. Current tall Parquet can remain while its
adapter is improved; dtype/clock requirements not expressible in the existing
schema require a versioned schema change, never silent casts or metadata guesses.

The NumPy manifest must enumerate schema version, recording dataset/source revision and
hash, run/source/group identity, models, layouts, timeline references, arrays,
dtypes/shapes, masks, enum meanings, units, coordinate conventions and provenance.
An illustrative NPZ inventory (names subject to implementation review):

```text
recording_info.json
timelines/cameras/sample_ids.npy
timelines/cameras/timestamps_s.npy
timelines/imu/sample_ids.npy
timelines/imu/timestamps_s.npy
measurement_tensors/landmarks/measurement_values.npy
measurement_tensors/landmarks/entry_presence.npy
measurement_tensors/imu/measurement_values.npy
measurement_tensors/imu/entry_presence.npy
static/model_scales.npy
```

Each measurement tensor identifies its timeline and range in the manifest. NPY export uses
equivalent arrays and an external manifest. It must be possible to reconstruct
the selected recording dataset without the original Parquet or installed
producer packages. Export selection is explicit; it does not claim to contain
every retained run or operational runtime state.

Do not merge positions and quaternions into a new seven-component tensor in the
strict export unless that is the chosen runtime payload. A convenience combined
pose table may remain a separately named derived projection. Static model fits
are stored once, not broadcast into every frame.

Automatic export may reuse immutable in-memory measurement tensors only after successful
publication binds them to the exact published revision. Otherwise use the same
Parquet-backed reader as later on-demand export. Do not bypass publication,
provenance or stale-result checks to save a read. Output reload validation is
separate from array assembly and must be measured as such.

The current NumPy exporter requires one shared timeline, drops presence masks and
can combine segment poses. Therefore this is a new versioned contract. Existing
exports remain readable through explicit legacy adapters; absent information
must be reported as unavailable rather than fabricated. Do not silently change
existing key meanings. Wide CSV keeps its documented absent/null representation
and uses separate tables for incompatible timelines; joining is a requested
derived operation with a declared policy.

## Current scope

The rules and contract-definition work were approved in chat. The current scope
is to settle the interface and compliance map, not to implement the remaining
pipeline changes. See [the detailed compliance audit](tensor-contract-audit.md).

## Concrete tensor interface

The initial implementation should consolidate existing concepts rather than add
a wrapper for every noun above. Four core responsibilities are sufficient:
channel layout, sample timeline, measurement tensor, and recording dataset. Observation/pose/reconstruction objects are
typed compositions of measurement tensors plus prepared numerical operations.

### Identity and axes

- Channel layout: immutable `layout_id`, channel kind, ordered entity IDs and component
  IDs, units per component, reference-frame ID and numeric dtype. Entity IDs are
  scoped by source/model/instance, not assumed globally unique names.
- Source context: recording/run or live execution identity, sensor group, source and
  optional model/instance ID. Layout identity alone is not sample identity.
- Sample timeline: `timeline_id`, `clock_id`, epoch, `sample_ids: int64[F]` and
  `timestamps_s: float64[F]`. Epoch timestamps are relative to a declared origin
  so small intervals are not unnecessarily represented as large absolute floats.
  IDs and times increase strictly within an epoch; gaps are permitted.
- Measurement tensor: `channel_layout`, `source_context`, `sample_timeline`, `measurement_values: numeric[F,N,D]`,
  `entry_presence: bool[F,N,D]`, and optional declared quality/status arrays.
  A measurement tensor slice references the matching portion of the timeline. Static tensors
  have `measurement_values[N,D]` and no sample axis or artificial timestamps.
- Recording dataset: immutable inventory of measurement tensors, shared layouts/timelines, model
  definitions, static fits and provenance. Recording dataset identity is separate from a
  reusable run slot. A published recording dataset additionally binds a durable revision.

Generic channels use explicit sample/entity/component axes, even for a scalar
channel. Domain wrappers may expose a squeezed view for convenience. Distinct
native dtypes belong in distinct buffers; confidence does not have to be packed
into the position array. A synchronized camera axis may be assembled explicitly
as [camera,sample,point,component] for triangulation. Raw camera streams with
different timelines cannot share that sample axis without an explicit join.

### Missingness is not one boolean

Measurement values and measurement metadata occupy separate typed arrays. For
example, landmark coordinates use `measurement_values[F,P,3]` (float64), while
`entry_presence[F,P,3]` (bool) records whether each component entry exists.
If explicit validity is stored, `value_validity[F,P,3]` (bool) records whether
each component has an available numeric value. Validity implies presence. This
distinguishes an absent entry from an explicitly recorded unavailable value.
For floating coordinates, validity can instead be derived from entry presence
and finite values; do not maintain a redundant mutable validity cache. Nullable
integer channels need explicit validity because there is no NaN sentinel.

Quality information is separate again. If a source reports confidence per
coordinate, `confidence_scores[F,P,3]` matches the measurement shape. If the
source reports one confidence per landmark, use `confidence_scores[F,P]`;
`confidence_scores[..., None]` broadcasts over XYZ without storing three copies.
Likewise, `measured_support[F,P]` and `solver_status[F,S]` describe whole points
or poses. Their declared entity axes must match the associated measurement axes.
Unknown confidence is explicit, never invented from finite coordinates.

Thus, three same-shaped tensors are appropriate for genuinely component-level
values, missingness and quality. They are not a mandatory layout for every
channel. A boolean quality mask is an operation-specific acceptance decision;
numeric confidence scores and categorical solver status retain information a
single boolean would discard. Every stored companion tensor is included in the
strict NumPy representation, with its own dtype, axes and meaning.

Existing `present` fields have different meanings. The new interface must name
them explicitly rather than treating them as interchangeable:

| Meaning | Contract |
| --- | --- |
| Entry presence | `entry_presence` says that a component entry exists in this scientific product. False means absent; float payload is canonical NaN. |
| Null/unavailable value | A present float entry with NaN is explicitly unavailable. Nullable integer buffers require a separate component validity mask. |
| Geometric availability | `point_valid[F,P]` or `pose_valid[F,S]` states that a complete point/pose satisfies the operation's requirements. It does not replace component presence. |
| Measurement support | `measured_support[F,P]` distinguishes measured support from interpolated/inferred results even when both are finite. |
| Confidence and solver status | Numeric confidence and enum codes carry quality and provenance; zero confidence is not the same as a missing row. |

Float infinities are rejected for the current scientific coordinate channels.
Position operations requiring a complete XYZ triple reject or mask partial
triples explicitly. Generic saved-channel loading preserves component-level
missingness for inspection. Mapping's current `MappedLandmarkBatch.present` is
geometric availability; export's `ChannelArrays.present` is entry presence.
Renaming/converting these requires semantic checks, not a field-for-field copy.
An implicit all-present mask is allowed only as an explicit canonical encoding
with identical observable semantics; it must not be guessed from finite values.

### Small operation surface and allocation contract

| Operation | Required behavior |
| --- | --- |
| `frame_view(i)` | Read-only views of values, masks and domain fields, with shared metadata; numeric payload is not copied and names are not reindexed. |
| `slice_samples(start, stop)` | Read-only view with sliced timeline; keeps the storage owner alive. Repeated slicing is not repeated validation of the whole source. |
| `select_entities(plan)` | Reuses a prepared index plan. Contiguous ranges may be views; arbitrary gathers explicitly allocate one bounded output or fill a caller-owned destination. |
| `mutable_copy()` | Explicit owned writable result; mutations cannot change a published input. |
| `iterate_measurements(selection, budget)` | Selects contexts/time windows with bounded decoded memory; includes scratch/output costs in the budget. |
| `to_display(plan, out)` | Explicit precision/order conversion into reusable display buffers; no change to scientific inputs. |

These names describe interface behavior, not finalized signatures. Frame helpers
are lightweight facades over the same tensors, not a second per-frame numeric
store. Domain functions accept/return measurement tensors or owned numeric output buffers.
Prepared plans are keyed by full layout/model identity, not just array size.

A producer can transfer exclusive ownership of a contiguous builder into a
published measurement tensor. If other writable aliases remain, publication must copy once
or revoke them through a controlled owner. NumPy `writeable=False` on a view or
`frozen=True` on a dataclass alone does not prove exclusive ownership. The
read-only contract is for supported callers, not a security boundary against
hostile Python code. Memory-mapped data, Arrow buffers and worker transfers need
explicit lifetimes; no view may outlive a closed mapping or detached buffer.

### Stateful operations and independent packages

Forge's roll state should become numeric previous rotations [S,4], previous
availability [S], parent indices [S], and prepared rest/reference arrays. Process
time in order; vectorize independent segments/branches where the algorithm
permits. Chunking must preserve the same reset, missing-parent and terminal-twist
behavior. No claim that a path-dependent algorithm can be parallelized across
all frames independently.

Core owns timelines, recording dataset publication and cross-package adaptation. Tracker
owns observation/mapping math; Forge owns pose/kinematic math. They can expose
compatible array interfaces without importing core or one another. A boundary
adapter should bind metadata or expose views, not reconstruct a point dictionary.

## Contract acceptance examples

These are specified tests, not tests already implemented or run:

1. Given a measurement tensor with frame IDs [10,12], `frame_view(1)` returns sample 12 and
   shares numeric memory; selecting names does not reorder the underlying measurement tensor.
2. A contiguous slice shares memory. A noncontiguous gather declares allocation;
   changing a mutable result cannot change the published source or another view.
3. Absent, present-null, measured finite and inferred finite samples survive
   Parquet and strict NumPy round trips with their distinct masks/provenance.
4. Reordering entity/component labels without reordering values is rejected by
   layout checks; a cached plan for a different layout cannot be reused silently.
5. A 30 Hz camera and 200 Hz IMU preserve independent timelines in one recording dataset
   and export. Identical sample numbers across clocks do not imply alignment.
6. A clock reset starts another epoch. A request to combine unrelated clocks
   fails clearly until an explicit relation and sampling policy is provided.
7. Processing the same sequence as one measurement tensor or uneven chunks produces equivalent
   roll state and scientific results, including empty frames and missing parents.
8. Loading a selected Parquet context skips provably unrelated row groups; adding
   another retained run does not force full numeric decoding for that selection.
9. Runtime-to-NPZ-to-runtime preserves dtype, shape, finite values, NaN positions,
   masks, timelines, layouts and static definitions. Bitwise NaN payload identity
   and storage aliasing are not promised. No object arrays/pickle are required.
10. Scientific float64 -> display float32 is tested as an explicit lossy conversion;
    the original remains unchanged and finite values outside float32 range have
    a declared failure/masking policy rather than silently becoming infinity.
11. Repeated access to a loaded frame allocates no numeric payload or name maps;
    memory/transfer counters identify every remaining copy at a declared seam.
12. A measurement tensor with no samples is valid for selection/streaming; solvers requiring
    data reject it at their own interface. Static fits do not acquire a fake frame.

## Source evidence rechecked on 2026-10-28

- `freemocap/core/reconstruction/recording_reconstruction.py` retains per-frame
  `SkeletonReconstruction` objects despite dense recording inputs.
- `freemocap/core/recording/exports/arrays.py` provides `ChannelArrays` with
  values/presence, selective reads and two-pass frame/value assembly.
- `freemocap/core/recording/exports/wide_csv.py` enforces shared timelines and
  writes values without the presence mask; saved outputs are reloaded to validate.
- `freemocap/core/recording/data_descriptors/recording_descriptor.py` describes
  sensor-group clocks but does not yet implement the proposed clock registry.
- Earlier audit findings in playback, observation assembly and Forge adaptation
  remain work candidates, not current benchmark results. Recheck each task's
  source and installed dependency revision before implementation.

## Sequential implementation plan

Global 1 and Global 2 implementation and validation are complete. Global 3 is
next; internal acceptance cases above are not additional checklist tasks.

- [x] **Global 1 — Define FreeMoCap’s tensor contract:** establish layouts, identities, components, availability, ownership and independent timelines.
- [x] **Global 2 — Replace observation flattening and pose-object conversions with tensor interfaces.**
- [ ] **Global 3 — Unify Parquet saving and loading:** connect runtime tensors directly to recording publication and selective saved-data readers.
- [ ] **Global 4 — Make NumPy exports match runtime tensors:** preserve layouts, companion arrays and timelines in NPY/NPZ; produce wide CSV through batched conversion.
- [ ] **Global 5 — Fix playback startup and frame delivery:** replace scalar-object Parquet decoding and repeated frame conversions/copies.
- [ ] **Global 6 — Fix the Three.js rendering path:** replace numerical dictionaries and repeated geometry repacking with prepared arrays and batched GPU updates. **Trails remain outside this scope.**
- [ ] **Global 7 — Finish downstream integration and prove the result:** validate remaining consumers and measure correctness, playback readiness, processing/export time and memory.

One sub-agent per approved task, with integration review and validation before
starting the next. Core owns integration contracts. Tracker and Forge remain
independent; neither imports the other or core. Dependency changes require
separate repository stages, branch preflight and human commit/push confirmation
before downstream refresh. Agents do not mutate Git state.

Baseline measurement and fixture design are internal work of the affected tasks;
no speedup is promised without measurements. Completed runtime changes and their
measurements are recorded above; remaining checklist items are planned work.
