# Camera Geometry Matching — Current Workflow

**Code snapshot:** September 10, 2026, working-tree implementation.

## 1. Purpose and inputs

The matcher assigns each observation source to a camera model from an existing calibration.

| Input | Contents |
|---|---|
| Sources | Live camera IDs or recorded-video source IDs |
| Calibration | Camera IDs, image dimensions, intrinsics, distortion, and extrinsics |
| Observations | Frame number, image dimensions, named 2D points, visibility scores, and detector stages |
| Initial assignment | An existing source-to-calibration-camera mapping, when available |
| Configuration | Sampling requirements, geometric thresholds, search limits, and failure policy |

The matcher evaluates camera assignments. It does not solve new intrinsics or extrinsics.

```text
Observations + existing calibration
                 ↓
          Select sample points
                 ↓
        Build pixel sample array
                 ↓
      Evaluate initial assignment
                 ↓ if not accepted
       Search camera assignments
                 ↓
        Validate search result
                 ↓
     Apply workflow-specific policy
                 ↓
      Source → camera model mapping
```

## 2. Shared observation preparation

### Point names

Detector stages are flattened into named points. Each name includes its stage prefix, such as `body.left_shoulder`. Child stages are included in this traversal.

For each sampled frame, point selection:

1. Collects finite 2D points whose visibility meets `minimum_point_visibility`.
2. Finds names present in at least two sources.
3. Adds the minimum participating visibility to that name's accumulated score.
4. Sorts names by descending score, then by name.
5. Retains up to **64 names**.

Real-time selection uses the observations available when its sample window is created. Posthoc selection uses the frames sampled across the recording.

### Pixel array

The selected observations become an array with axes:

```text
[source, sampled frame, point name, x/y]
```

- Missing points and points below the visibility threshold become `NaN` pairs.
- Source sets, synchronized frame numbers, and image dimensions are checked during extraction.
- Duplicate qualified point names cause an error during extraction.
- Source image dimensions must exactly match a candidate calibration camera's dimensions for that pairing to be considered compatible.

## 3. Shared matching and scoring

### A. Establish usable source pairs

Sampled frames are divided into alternating subsets: one for search and one for validation.

A source pair is included when both subsets contain enough frames with enough shared points. The included pairs must connect the complete source set. Otherwise, the result is `insufficient`.

When automatic matching is disabled, the shared evaluator returns `disabled` with the compatible initial assignment, if present.

### B. Check the initial assignment

The initial assignment is evaluated on both subsets. If both return acceptable fitness, matching returns `initial_accepted` without searching other assignments.

### C. Calculate geometry fitness

For a specified assignment, the evaluator:

1. Identifies points observed by at least two cameras.
2. Checks the required frame and point counts for each camera.
3. Undistorts observed pixels and constructs viewing rays.
4. Excludes points without a camera pair meeting the ray-angle criterion.
5. Triangulates with outlier rejection disabled.
6. Checks finite reconstruction, positive camera depth, and finite reprojection error.
7. Calculates each camera's valid fraction, median error, and 90th-percentile error.

Reprojection errors are expressed as pixels at a **1,000-pixel image diagonal**. Missing observations are excluded from the observed-point count. Observed points with invalid reconstructed geometry contribute infinite error.

Fitness is `acceptable` only when every camera meets all three configured limits. Otherwise, it is `poor`. Insufficient frame or point counts produce `insufficient`.

The evaluator also calculates a search cost: squared normalized errors are averaged across participating cameras, divided by the squared p90 threshold, capped at 1 per point, and averaged by frame.

### D. Search and validate assignments

If the initial assignment does not pass:

1. Score ordered pairs of calibration cameras for each supported source pair.
2. Search assignments in which each source receives a distinct calibration camera.
3. Use lower bounds to prune branches and retain the two lowest-cost complete assignments.
4. Stop expanding branches at the configured search-node limit.
5. Evaluate the best assignment on the validation subset.
6. Compare the best and second-best assignments on search and validation costs.

| Status | Condition |
|---|---|
| `disabled` | Automatic matching is off |
| `insufficient` | Required observation support is absent |
| `initial_accepted` | Initial assignment passes both subsets |
| `matched` | Search winner passes fitness and separation checks |
| `ambiguous` | Best and second-best candidates are closer than the required score gap |
| `poor` | No candidate is available, or the search winner does not pass validation fitness |
| `search_limit` | Assignment search stops before completion |

A result contains a status, an assignment when available, fitness diagnostics when available, and search details when a search was performed.

## 4. Real-time workflow

### Initial camera binding

The calibration tracker first attempts to bind live cameras by exact camera ID. If that does not cover every live camera, it attempts a structured camera-index mapping.

The index mapping must cover all live cameras, use distinct calibration cameras, and pass the ID-overlap checks. Otherwise, the binding is unmatched.

### Observation collection

The real-time aggregator combines each camera's skeleton and ChArUco observations. Frame numbers and image dimensions must agree, and stage names must not overlap.

When triangulation is enabled, the aggregator calls the live matcher. The matcher collects samples when:

- Automatic matching is enabled and a calibration is loaded.
- Observations cover the configured source set, with at least two sources.
- No top-level stage reports more than one bounding box.
- The matching lifecycle is not suspended.

The sample window:

- Selects its point-name layout when created.
- Retains that layout until reset.
- Samples at intervals of at least **0.2 seconds**.
- Holds `max(24, 2 × minimum_frames)` sampled frames.

### Background evaluation

Once the window is full, its numeric snapshot is submitted to a single background thread. The initial assignment comes from the calibration tracker's current applicable binding.

The window is cleared after submission. Observations can continue filling it while the request runs. A second request is not submitted while one is outstanding.

Completed requests carry attempt and generation identifiers. Results from an earlier generation are not applied. Worker exceptions propagate when the future is read.

### Applying the result

| Result/policy | Calibration tracker action |
|---|---|
| `initial_accepted` or `matched` | Install the assignment as a geometry binding and clear subset-triangulator caches |
| `insufficient` | Leave the binding unchanged |
| Other result + `continue` | Retain the current binding |
| Other result + `stop` | Raise an error |

The live matcher returns a change flag when a completed result contains both an assignment and search details. The aggregator uses this flag to reset keypoint filtering, point gating, skeleton fitting, and reconstruction-observability tracking.

If the calibration contains fewer cameras than the live source set, the live matcher produces `poor`, applies the failure policy, and returns the change flag.

### Lifecycle

| Event | Next state |
|---|---|
| Initialization or reset | Collecting |
| Submit evaluation | Running |
| Insufficient result | Collecting |
| Accepted result | Monitoring; further evaluations can run |
| Poor, ambiguous, or search-limit result | Suspended |
| Calibration generation or matching configuration changes | Reset lifecycle, sample window, and initial binding |

Closing the matcher shuts down its executor and reads any completed, non-cancelled future.

## 5. Posthoc workflow

Posthoc mocap processing uses observations collected from recorded videos.

1. Load the selected calibration for a multi-camera recording.
2. Choose evenly spaced frames across the recording, including its endpoints.
3. Select up to `max(24, 2 × minimum_frames)` frames, limited by recording length.
4. Select point names using those sampled frames and construct the pixel array.
5. Replace a sampled frame's pixels with `NaN` if any top-level stage reports multiple bounding boxes.
6. Build an initial assignment only if every video source ID matches a calibration camera ID.
7. Run the shared matching evaluator synchronously.
8. Resolve the returned assignment into `source ID → camera model`.
9. Use that mapping for reconstruction of the recording's observation buffers.

### Posthoc result policy

- **No assignment:** raise an error, regardless of failure policy.
- **Stop:** accept only `initial_accepted`, `matched`, or `disabled`; raise for other statuses.
- **Continue:** use the returned assignment, including a provisional assignment.

Posthoc processing does not use the live matching lifecycle or background executor.

## 6. Other processing paths

| Path | Matching behavior |
|---|---|
| Single-camera posthoc mocap | Uses planar projection; does not run multi-camera assignment search |
| Real-time without calibration | Does not collect geometry-matching samples |
| Real-time with automatic matching disabled | Retains the tracker's ID/index binding; does not submit geometry searches |
| Calibration solving | Produces camera models; the matcher consumes those models afterward |
| Client page restoration | Reads the running configuration and calibration; does not invoke the matcher directly |

## 7. Current default settings

| Setting | Default |
|---|---:|
| Automatic matching | Enabled |
| Failure policy | Continue |
| Minimum point visibility | 0.5 |
| Minimum qualifying frames per subset | 6 |
| Minimum shared points per qualifying frame | 6 |
| Minimum valid fraction per camera | 0.9 |
| Minimum ray angle | 1° |
| Maximum median normalized error | 2 |
| Maximum p90 normalized error | 5 |
| Maximum search nodes | 250,000 |
| Minimum candidate score gap | 0.05 |
| Point-name limit | 64 |
| Real-time sampling interval | 0.2 seconds |
| Frame-window size at defaults | 24 |

## 8. Implementation locations

Paths below are relative to `freemocap/core/`.

| Responsibility | File |
|---|---|
| Real-time observation assembly and reconstruction resets | `pipeline/realtime/realtime_aggregator_node.py` |
| Initial live camera binding | `tasks/calibration/shared/calibration_camera_binding.py` |
| Calibration state and result application | `tasks/calibration/shared/calibration_state.py` |
| Point selection and sample arrays | `tasks/calibration/camera_matching/observation_sampling.py` |
| Geometry fitness | `tasks/calibration/camera_matching/matching_fitness.py` |
| Shared evaluation workflow | `tasks/calibration/camera_matching/matching_evaluation.py` |
| Assignment search | `tasks/calibration/camera_matching/matching_search.py` |
| Real-time matching | `tasks/calibration/camera_matching/live_matching.py` |
| Live attempt lifecycle | `tasks/calibration/camera_matching/matching_lifecycle.py` |
| Posthoc matching | `tasks/calibration/camera_matching/posthoc_matching.py` |
| Posthoc integration | `tasks/mocap/posthoc_mocap_task.py` |
| Settings and result types | `tasks/calibration/camera_matching/matching_models.py` |
