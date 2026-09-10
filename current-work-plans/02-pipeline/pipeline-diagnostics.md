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

Rigid-body records are keyed by model ID and segment name. The payload declares millimeter or pixel length units. Unavailable scalar fields are omitted on the wire.

The client validates byte lengths against the declared axes. It retains the latest diagnostic delivery, replays it through the server-context subscription, and clears diagnostic state on disconnect.

## Posthoc persistence

Completed posthoc mocap processing writes **`diagnostics.npz` in the recording folder**.

The archive contains:

- Frame numbers.
- Full reprojection error, observation, reconstruction, and solver-weight arrays when available.
- Per-model frame × segment arrays with measured length, reference length, and residual columns.
- JSON metadata naming all axes, units, reference kinds, and per-camera/per-segment summaries.

The archive loads with `numpy.load(path, allow_pickle=False)`. Missing numeric values are NaN; unavailable summary values are JSON null. Live summaries can use the same `ResidualAccumulator`; the transport exposes frame measurements without selecting a display window.

## Validation

- Rejected points retain their diagnostic errors.
- Differently ordered point names across cameras produce the same associations.
- Missing observations remain distinct from unsuccessful reconstruction and zero error.
- Single-camera output has no reprojection diagnostics.
- Live residuals use the previous fit and clear their reference on reset.
- Posthoc residuals use the frozen recording fit.
- Saved arrays round-trip without pickle.
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
