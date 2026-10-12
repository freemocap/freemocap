# Simple math loops: opportunities and measured seconds saved

2026-10-12. Scope: the post hoc 3D fitting/reconstruction path, its installed
SkellyForge and SkellyTracker math, and adjacent filtering/timing calculations.
This is an inventory of the inspected path, not a claim that every math loop in
all repositories has been found. GPU inference batching is excluded.

## Inventory

| What we calculate | What the code repeats | Calculate together instead | Status / priority |
| --- | --- | --- | --- |
| Whether each XYZ point is present | `isfinite` and `all` once per point, twice per recording | One array check per frame; preserve named point views | Implemented in core, measured below |
| Joint attachment offsets | One quaternion-vector rotation per connected joint per frame | Paired arrays of rotations and attachment vectors | Real-data experiment below; SkellyForge change |
| Landmark world positions | One scale/rotation/translation per visible landmark per frame | Batched rotation and translation of all selected landmarks | Real-data experiment below; SkellyForge change |
| Single-vector rotations within temporal roll | Two generic cross products per tiny rotation | Specialized three-component arithmetic when dependencies prevent batching | Prior experiment saved 9.61 s; not vectorization, not installed |
| Validity of fitted lengths/scales | `isclose` per segment on every call to synthesis | Arrays of lengths/scales; one finite/positive/close mask | Straightforward candidate; savings not measured |
| Parent-relative rotations | Quaternion conjugation and multiplication per joint | Existing batch conjugation/Hamilton-product helpers after world rotations are solved | Candidate; preserve selected segments, names and provenance |
| Joint angles | Euler decomposition per joint | Group joints by their exact Euler convention and batch each group | Candidate; preserve singularity branches and zero offsets; more testing |
| Segment directions and lengths | Displacement, norm and direction alignment per segment per frame | Batch segments with the same observation/solver pattern | Higher potential; missing/degenerate/rigid-fit branches make it less simple |
| Anatomical landmark offsets | Means, norms, cross products per mapping entry and frame | Pre-index mappings; batch independent offsets over frames | SkellyTracker candidate; preserve missing-input and handedness rules |
| Segment and whole-body centers of mass | Small weighted vector sums per segment/frame | Gather present points and perform weighted array reductions | Candidate; preserve missing mass/landmark rules and reduction precision |
| Segment length residuals | One difference/ratio per available segment | Batch validated measured/reference length pairs | Small candidate; construction of diagnostic objects remains |
| Trajectory filtering | A filter call per point's contiguous valid run; three interpolation calls per run | Group points with identical valid intervals and sample grid | Already filters XYZ together; grouping is possible, but original full filter was only ~0.20 s |
| Mean camera timestamps | Python sum per frame | Array mean over the camera axis | Small setup-only candidate; not a reconstruction bottleneck |

Installed source evidence: quaternion and temporal state [@skellyforgeQuaternionMath2026];
tracker mapping and state [@skellytrackerBatchSessions2026]. Also inspected
SkellyForge `chain/synthesis.py`, `pose/hydration.py`, `pose/model_scale_fitting.py`,
`linkage/joint_pose.py`, `pose/rigid_body_diagnostics.py`, and biomechanics
`center_of_mass.py` / `composite_inertia.py` at the same installed revision.

Do not flatten temporal roll or parent-origin traversal into an unordered batch.
Those loops enforce dependencies. Batch the independent arithmetic around them.
The synthesis experiment retains the original origin traversal, validation,
Point construction, and public type-checking wrapper. It does not use the prior
specialized scalar rotation replacement.

## Change 1: check every point in a frame together

Implementation: `freemocap/core/reconstruction/posthoc_reconstruction.py`,
`_finite_frame_points`, used by both fitting and reconstruction.

Before: each point triggered a separate NumPy finite check and reduction.
After: `np.isfinite(frame).all(axis=1)` checks all XYZ points together; the remaining
loop only constructs the same named dictionary of array views.

Sample recording, all 1,108 frames, three alternating repetitions:

| Work timed | Before | After | Seconds saved |
| --- | ---: | ---: | ---: |
| Build the valid-point dictionaries for one pass | 0.5204 s | 0.0386 s | 0.4818 s (92.6%) |

The same preparation occurs in two passes. Approximately 0.96 s is the sum of
those isolated savings, not a measured complete-pipeline saving. Every selected
point and coordinate matched exactly. A focused test covers NaN, infinities,
strided arrays, empty/all-missing frames, order and preservation of array views.

## Change 2: rotate attachment offsets and landmarks together

Diagnostic implementation only, inside the benchmark process. The dependency
installation and checkout are unchanged. Arrays contain corresponding quaternion
and vector rows, not the N-by-M product of every quaternion with every vector.
Collection into arrays and conversion back to named objects are included in timing.
Each reconstruction starts with fresh temporal state and the same original frozen
model fit; fit and input reading are outside the reconstruction timer.

The full returned human reconstruction is checked: 1,839,480 numeric values per
run, plus dictionary keys, array shapes, missing fields and other metadata.
Tolerance: absolute 1e-8, relative 1e-10, matching NaNs. This does not cover board
models or every malformed-input case in an upstream production test suite.

Local evidence (ignored): `.test-artifacts/performance/math-loops/` contains the
original core source snapshot, candidate synthesis, real-data comparison script,
point-check timings and reconstruction timings. No output files were overwritten.

## What happens next

The core point-check change is a normal unstaged source/test diff. The two
rotation-loop changes are a measured SkellyForge proposal, not production code
hidden inside core. The workspace requires independent repository stages and a
human commit/push handoff before downstream dependency integration. SkellyForge
branch/status inspection was also refused by Git's ownership check; no Git
configuration was changed to bypass it.

Before installing the rotation change upstream: retain the public validation
contract; add focused synthesis tests for empty/partial/disconnected selections,
invalid fits, backward traversal and landmark ownership; test the board model;
then repeat complete-pipeline scientific parity and timing. The current experiment
proves the human reconstruction speedup on this recording, not all those cases.

The previous single-vector arithmetic experiment and this batching experiment
optimize overlapping work. Their saved seconds must not be added together.


## Measured reconstruction time (1,108 motion-capture frames)

Two runs per version, in order original / core / batched / batched / core / original.
All 1,839,480 numeric output values matched **exactly** on every run.

| Version | Run 1 | Run 2 | Median seconds |
| --- | ---: | ---: | ---: |
| Original | 32.151 | 31.700 | 31.926 |
| Check points together | 30.934 | 30.580 | 30.757 |
| Check points together + rotate attachments and landmarks together | 25.548 | 24.607 | 25.077 |

Rotating attachments and landmarks together saved **5.68 seconds**, or **18.5%**, relative to the version with batched point checks. Combined, these candidates saved **6.85 seconds (21.5%)** against original reconstruction in this experiment.

These are human reconstruction seconds, not full pipeline seconds. Only two runs per version; ordinary host variability remains. The end-to-end core-only difference exceeds its isolated point-check saving, so do not attribute that entire difference to the point-check change. Lightweight unit tests overlapped part of the first original run; the reverse-order original run was also slower than both batched runs.

Validation: 17 focused core tests and 8 bibliography tests passed; bibliography
validator reported zero errors. Two additional pytest-based reconstruction suites
could not load because pytest is absent; no dependencies were installed. Real-data
reconstruction comparisons above completed successfully. Generated measurements
remain ignored and source changes remain unstaged.
