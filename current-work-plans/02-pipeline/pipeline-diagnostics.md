# Pipeline diagnostics

## Implemented measurements

| Measurement | Owner | Produced by |
|---|---|---|
| Per-camera reprojection errors, observation masks, finite reconstruction masks, solver weights | FreeMoCap | `Triangulator.triangulate()` |
| Measured segment length, reference length, signed residual | SkellyForge | `measure_rigid_body_residuals()` |
| Count, unavailable count, bias, RMS, population standard deviation | SkellyForge | `ResidualAccumulator` |

These records contain measurements. They do not choose camera assignments, reset the pipeline, or classify a calibration as healthy or unhealthy.

## Reprojection data

- `TriangulationResult.diagnostics` retains arrays before downstream rejection, filtering, or coordinate transformation.
- Array axes are **camera × point** for live calls and **camera × frame × point** for batch calls.
- Errors retain the triangulator's input units: `pixels` or `normalized`.
- Observation presence and finite reconstruction are separate masks. A missing error is not a zero error.
- Solver weights describe contribution to the reconstruction, not detector confidence.
- Per-camera summaries expose observed, reconstructed, and contributing counts, plus mean, RMS, and maximum finite error.
- Single-camera planar projection has no reprojection diagnostic record.
- The live adapter aligns camera observations by qualified point name and retains diagnostics for points rejected from the published reconstruction.

## Rigid-body data

Each segment record contains:

| Field | Meaning |
|---|---|
| `measured_length` | This pose's segment scale estimate multiplied by its authored segment length |
| `reference_length` | The reference fit's segment length |
| `residual` | Measured length minus reference length |
| `reference_kind` | `prior_live_fit` or `recording_fit` |

FreeMoCap uses the existing mapping-based measured-segment selection. Segments without measured evidence retain unavailable measurements and residuals, even if the model provides a reference length.

Measurements use the pose reconstructed from the pipeline's reconstruction input, including any configured filtering. For direction-based segments the scale estimate comes from endpoint separation; rigid-fit segments use the pose hydration fit's scale estimate.

### Real-time reference

The diagnostic reference is the fit from the preceding reconstructed frame. It is retained in reconstruction state so diagnostics do not run a second scale fit. The first frame after initialization or reset has no reference residual.

### Posthoc reference

The shared reconstruction function receives the frozen recording fit. Every evaluated frame uses that fit. These are residuals against the recording's fitted reference, not a held-out validation score.

## Live integration

```text
Triangulator → AngulationResult → aggregator output
SkellyForge residuals → SkeletonReconstruction → aggregator output
                                      ↓
                           FrameMessage.diagnostics
                                      ↓
                     TypeScript validation and transport
                                      ↓
              useServer().subscribeToDiagnostics(callback)
              useServer().getLatestDiagnostics()
```

Each diagnostic delivery includes its frame number. Reprojection blocks carry source IDs, qualified point names, units, column names, and little-endian float32 bytes. Columns are `error`, `observed`, `reconstructed`, and `weight`.

Diagnostics are an optional field of the existing frame message on the existing connection. Client subscriptions are local listeners for that field, not separate network subscriptions or streams.

Rigid-body records are keyed by model ID and segment name. The payload declares millimeter or pixel length units. Unavailable scalar fields are omitted on the wire.

The client validates byte lengths against the declared axes. It retains the latest diagnostic delivery, replays it through the server-context subscription, and clears diagnostic state on disconnect.

## Posthoc persistence

Diagnostic measurements are required channels in the canonical **`{recording_name}_data.parquet`**. Every canonical publication also generates **`output/diagnostics.yaml`** from that Parquet, covering all retained runs and identifying the selected run.

### Physical Parquet columns

The existing scalar-row schema is unchanged: `timestamp_s`, `sensor_group`, `frame_number`, `source`, `reference_frame`, `channel`, `name`, `component`, `value`, `units`, `run_id`.

| Channel | Source / name | Components | Units | Owning stage |
|---|---|---|---|---|
| `REPROJECTION_ERROR` | Camera / qualified tracker keypoint | `error` | `px` or `1` for normalized coordinates | Triangulation |
| `RECONSTRUCTION_COVERAGE` | Camera / qualified tracker keypoint | `observed`, `reconstructed` | `1` (0 or 1) | Triangulation |
| `TRIANGULATION_WEIGHTS` | Camera / qualified tracker keypoint | `weight` | `1` | Triangulation |
| `RIGID_BODY_RESIDUALS` | Model instance / segment | `measured_length`, `residual` | `mm` or `px` | Reconstruction |

All rows use the synchronized recording grid. Missing numeric measurements are Parquet nulls. Observation presence and finite 3D reconstruction remain distinct flags: a reconstructed point may lack an observation in a particular camera. Solver weights are not detector confidence. Full arrays are retained without diagnostic sampling.

Fixed segment references are stored once in the run's existing scale-fit descriptor. Rigid-body channels identify that fit by run, group, source, and spatial reference; publication checks each reading against the stored fit. Stage invalidation removes the corresponding diagnostic channels and rows while preserving other runs.

### YAML report

The frozen Pydantic `RecordingHealthReport` declares its schema version, recording identity, exact Parquet SHA-256, selected run, run descriptors' hashes, source/model identities, scale fits, and assessment criteria.

Each camera/keypoint/component or model/segment/component entry records frame and time bounds, units, finite and unavailable counts, mean, RMS, population standard deviation, minimum, maximum, and an assessment. For coverage flags, the mean is the fraction of frames for which the flag is true; the finite count is the number of stored flags, not the number of successful observations.

Assessments are `not_assessed` without configured quality criteria, `insufficient_data` without enough finite samples, or `pass`/`fail` against explicitly supplied RMS and availability criteria. Automatic publication supplies no quality thresholds. No overall calibration-health verdict is inferred.

`build_recording_health_report(path=..., criteria=...)` regenerates and reassesses solely from Parquet. `write_recording_health_report(structure=..., criteria=...)` writes YAML; its caller holds the recording write lock. Report output errors propagate. Parquet replacement is atomic; YAML replacement is atomic separately. A report failure after Parquet publication leaves the current data and no prior report rather than a stale report presented as current.

`MeasurementAccumulator` and `assess_measurement` are shared building blocks for live windows. The live transport currently exposes frame measurements; a running assessment window and display policy have not been selected.

## Validation

- Rejected points retain their diagnostic errors.
- Differently ordered point names across cameras produce the same associations.
- Missing observations remain distinct from unsuccessful reconstruction and zero error.
- Single-camera output has no reprojection diagnostics.
- Live residuals use the previous fit and clear their reference on reset.
- Posthoc residuals use the frozen recording fit.
- Diagnostic channels round-trip through the canonical scalar Parquet schema, preserving nulls and identities.
- YAML validates against the report model and regenerates from saved measurements.
- Stage invalidation removes dependent diagnostics while preserving other runs.
- Mismatched residual references fail before replacing either output.
- A browser decodes a backend-generated diagnostic frame without earlier frames, then clears it on disconnect.
- Existing triangulation, reconstruction, recording-checkpoint, and message tests pass.

## Development environment

FreeMoCap's `.venv` uses an editable installation of the sibling `skellyforge` checkout for the shared residual implementation. The dependency manifest still identifies the remote development branch; syncing that manifest can replace the editable installation. No Git state was changed.

## Next workflow decisions

1. Which summaries and time windows to display during streaming.
2. How recording review should expose diagnostic timelines and source coverage.
3. Which conditions should produce health classifications, independently of measurement generation.
4. How candidate camera assignments consume these diagnostics using equivalent inputs and independent reconstruction state.

No health classification or geometry-matcher policy is implemented by this diagnostic layer.
