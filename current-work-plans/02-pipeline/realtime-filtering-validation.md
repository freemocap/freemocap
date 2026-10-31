# Realtime temporal processing

The aggregator owns temporal processing for both centralized and per-camera
inference. Detectors supply raw predictions; camera workers do not maintain a
second, separately configured point smoother.

## Processing contract

1. Admit finite image coordinates above the detector confidence threshold.
2. Optionally apply One Euro smoothing in pixel coordinates, independently for
   each camera. Image predictions are never gap-filled before triangulation.
3. Triangulate accepted image predictions and reject excessive reprojection error.
4. Reject excessive spatial velocity before updating the spatial smoother.
5. Optionally smooth spatial coordinates with One Euro.
6. Predict missing spatial coordinates for a bounded duration, then hold the
   predicted endpoint until the point visibility limit expires.
7. Hydrate segment poses, fit dimensions using only current accepted input,
   and retain unavailable poses for a bounded duration before connected placement.

Image filters use each camera's capture timestamp; spatial processing uses the
joined frame's capture timestamp. Reference replay preserves recorded intervals
and camera offsets. Processing speed does not become signal time. Durations use
seconds internally and milliseconds in the UI. At 6 FPS, a 100 ms retention limit
cannot bridge even one missing sample; that is expected, not a frame-count bug.

Single-camera spatial positions are pixels, so millimetre velocity thresholds and
millimetre smoothing coefficients are not applied to that representation.

Accepted input history is separate from generated output. Prediction cannot
refresh its own observation age. Velocity decay is integrated analytically over
elapsed time, making the result independent of missing-frame frequency. After an
expired gap, finite input initializes fresh smoother state. Config toggles,
detector changes, and calibration changes reset the corresponding history.

All point and pose calculations use the existing dense arrays and Forge tensors.
Numerical state and work arrays are reused for unchanged entity layouts. Published
results own their arrays: overwriting working memory must not change a frame
another consumer is still reading. Temporal frame traversal is ordered; entities
and components are processed with array operations.

## Configuration and representation

`RealtimeFilterConfig` is the backend definition. `GET /realtime/filter-config`
returns defaults, requested settings, and settings from the latest completed
worker frame. `PUT` changes filter settings without configuring cameras. The UI
does not report a queued request as applied; it waits for worker frame evidence.
Updates preserve history when only coefficients change. The former frontend
FABRIK and frame-count controls were not supported by this processing path and
have been removed. Posthoc controls now edit their actual Butterworth settings.

Temporal status accompanies streamed numerical values: unavailable, current
input, predicted support, or retained value. Current input can still be a model
prediction; this classification does not turn it into an empirical measurement.
Weighted attachment placement couples model translations, so model outputs with
generated support are conservatively marked accordingly. Generated inputs do
not update the fitted body dimensions.

## Reference comparisons

Commands use the existing environment and prepared recordings, without cameras:

```text
.venv/Scripts/python.exe -B -m freemocap.tests.reference_recordings.temporal_comparison
.venv/Scripts/python.exe -B -m freemocap.tests.reference_recordings.temporal_comparison --controlled-only --image-beta 0.0001 0.003 0.01 0.03 --output .test-artifacts/filter-audit/controlled-sweep.json
```

Both recordings contain the same session at different sampling rates: test data
has 222 frames at 6 FPS; sample data has 1,108 frames at 30 FPS. They are not
independent subjects or motion ground truth. Profiles share identical saved
detector inputs, calibration, perturbations, and numerical processing code.

The recorded-input experiment adds independent, seeded 2 px image noise, removes
both shoulder predictions for 250 ms, and removes every prediction for 400 ms
and 800 ms. Its recovery error is deviation from undisturbed triangulation over
recovered cells, not independently measured anatomical error. Different duration
limits recover different subsets of cells, so their errors are not a comparison
on an identical time interval.

With 3D smoothing on the 30 FPS recording:

| Visibility limit | Missing segments relative to reference coverage | Recovery deviation RMS |
| --- | ---: | ---: |
| No recovery | 4.23% | Unavailable |
| 100 ms | 3.31% | 9.04 mm |
| 300 ms | 1.70% | 16.03 mm |
| 500 ms | 0.85% | 27.39 mm |

The controlled experiment projects known stationary positions and a 100 mm
vertical step through the reference calibration, adds 1 px Gaussian noise,
and processes at 30 Hz. Jitter is RMS deviation from each point's stationary
temporal mean; absolute error is reported separately in the JSON. The following
uses the selected optional image coefficient, beta = 0.03 inverse pixels:

| Smoothing | Stationary jitter | Time to 90% of step |
| --- | ---: | ---: |
| None | 1.64 mm | 0 ms |
| Image only | 0.53 mm | 67 ms |
| Spatial only | 0.50 mm | 67 ms |
| Image and spatial | 0.33 mm | 100 ms |

These are filter response times, not camera-to-screen latency. The former image
coefficient of 0.0001 produced 367 ms image-only delay and 400 ms combined delay.
Coefficient tuning matters; these results do not establish that image smoothing
is inherently inferior. One Euro's coefficient units and slow/fast tuning
procedure follow [@casiezOneEuroTuning]. Other pipelines support filtering image
and world outputs separately [@mediapipePoseTemporalFiltering]; offline
regularization results do not establish a causal realtime default
[@karashchukAnipose2021].

## Selected defaults

- Image smoothing off, with beta 0.03 inverse pixels when enabled.
- Spatial smoothing on: minimum cutoff 1 Hz, beta 0.01 inverse millimetres,
  derivative cutoff 1 Hz.
- Point visibility and segment retention limits 300 ms.
- Prediction motion limit 100 ms, velocity half-life 80 ms.
- Velocity rejection 50,000 mm/s, with 300 ms reacquisition timeout.
- Reprojection limit 60 px; body scale fitting window 30 accepted-frame slots.

The default spatial temporal stages took approximately 0.26 ms median and
0.34 ms at the 95th percentile in the sample replay. This includes image
admission and spatial filtering, but excludes triangulation, skeleton solving,
inference, transport, and rendering. The 30-frame spatial allocation probe kept
the same state/work array identities, with approximately 18.4 KiB peak traced
allocation and 0.4 KiB retained. This is not a claim of allocation-free execution.

Ignored JSON reports contain complete settings, metrics, and source hashes.
The final visual judgment still requires the application's live view. Users can
try combined smoothing or 500 ms retention without restarting the pipeline.

## Integration and recording checks

The 222-frame test recording passed all eight real-worker combinations of
centralized/per-camera inference, human tracking on/off, and explicit/latest
calibration selection. Each run changed filter settings at frame 55, confirmed
the requested values in completed outputs, preserved capture intervals and raw
observations, and released its workers and shared memory.

Live settings survive calibration recording's temporary detector pause. Startup
failure tests cover cleanup without terminating shared services; malformed replay
timing closes opened videos before shared memory is allocated.

Realtime filtering affects live presentation. Mocap recording saves camera videos;
posthoc processing uses its own Butterworth settings and does not reuse generated
live positions as detector evidence. The provenance reprocessing tests passed on
copies of both prepared recordings: source observations, raw triangulation,
timestamps, and their stage provenance stayed unchanged when filtering reran.
The full-rate sample's batched filter also matched the scalar reference.

Temporal status survives CBOR decoding, channel resolution, and pooled transfer
into the viewport worker. Every completed frame replaces the previous model set,
including explicit missing values. The existing one-second timeout applies only
when no new frame arrives; it no longer fills missing input behind the backend's
back. The server sends complete reconstruction frames while a pipeline runs and
camera-only frames when no pipeline is active.
