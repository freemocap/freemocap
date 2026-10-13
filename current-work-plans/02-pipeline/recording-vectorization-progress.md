# Recording vectorization progress

2026-10-12. Core integration only; no dependency or realtime changes.

- [x] Replace per-frame fitting hydration and streaming scale accumulation with installed Forge `LandmarkPoseGeometry.recover` and `fit_model_scale_arrays`.
- [ ] Batch tracker-to-landmark mapping; its current scalar interface still requires frame dictionaries.
- [ ] Recover reconstruction poses in batches before temporal roll resolution.
- [ ] Restrict sequential processing to actual roll-history dependencies, preserving resets on empty frames.
- [ ] Batch connected skeleton placement, joint rotations, residual diagnostics and center of mass after roll resolution.
- [ ] Compare full saved output channels and end-to-end pipeline latency after reconstruction integration.

## First measured change

Saved inputs from the existing paired-reference recordings were loaded through
`read_saved_reconstruction`, preserving measured-only fitting support. The exact
pre-edit fitting function was retained in an ignored diagnostic file and run on
the same in-memory requests. Single unprofiled execution per implementation/model;
times exclude loading and do not predict concurrent full-pipeline savings.

| Dataset/model | Before s | After s | Speedup |
| --- | ---: | ---: | ---: |
| Test human | 1.714 | 0.878 | 1.95x |
| Test board | 0.084 | 0.042 | 2.00x |
| Sample human | 7.573 | 3.678 | 2.06x |
| Sample board | 0.294 | 0.131 | 2.23x |

Fitted scale, every segment scale and length: maximum absolute difference **0**.
Input identities and measured/voting segment sets also matched. This is fitting
parity, not a claim of a newly rerun full pipeline comparison.

Four focused tests passed: scalar-vs-batch fitting, no-observation behavior,
repeatable saved reconstruction refresh, and failed-refresh preservation.
Ruff passed for the changed implementation and new test. Diagnostic evidence:
`.test-artifacts/vectorization/fitting-results.json` and `benchmark.py`.

Remaining limitations: fitting still maps and packs scalar frame dictionaries;
Forge hydration batches frames but dispatches different segment solvers in a
definition-level loop. Reconstruction still uses the prior per-frame driver.
No claim that all math loops have been removed. The pre-existing reference
benchmarks remain untouched.


## Core integration after SkellyTracker publication

Published remote branch, core lockfile, and installed distribution all resolve to
`700599ba874c8a243df3513e4cc1bf191ebf9b03`. No environment refresh was needed.

Fitting now calls PreparedTrackerMapping over the recording arrays; per-frame
mapping and dictionary packing have been removed from fitting. Before/after
single measurements on the preserved real reference input (old scalar fitting
versus current fitting; input loading excluded):

| Dataset/model | Before seconds | After seconds | Maximum absolute fit difference |
| --- | ---: | ---: | ---: |
| Test human | 1.461772 | 0.090534 | 9.095e-13 |
| Test board | 0.071716 | 0.021800 | 0 |
| Sample human | 7.527765 | 0.133764 | 2.274e-13 |
| Sample board | 0.338967 | 0.071553 | 0 |

These differences pass the existing diagnostic tolerance; they are no longer
bit-identical for human fits. Do not describe these as full-pipeline timings.
Local evidence: `.test-artifacts/vectorization/fitting-results.json`.

Shared reconstruction now uses `SkeletonReconstructionState.map_frame` to retain
one prepared mapping for the current bundle. A new bundle replaces the plan;
empty observations and temporal-state resets reuse the unchanged definition.
Scene points belonging to other bundles are filtered to the bundle's declared
axis. Direct pass-through mappings retain the scalar fast path. No detector,
roll-resolution, confidence, or WebSocket behavior was changed.

Twenty focused tests passed: fitting, saved reconstruction refresh, state reuse,
configuration replacement, both human trackers' hand reconstruction, missing-hand
reentry and anchor handling. An initial test fixture path failed; the suite passed
with a shorter ignored temporary path. Existing type-only-import lint findings
remain in reconstruction/test modules; fitting and reconstruction-state files
passed lint. Live-camera timing and a new complete pipeline comparison remain
outstanding, as do batched reconstruction preparation and downstream math.


## Batched reconstruction preparation experiment � not enabled

Prepared mapping and LandmarkPoseGeometry were evaluated in bounded chunks of
256 frames before the unchanged sequential roll resolver. Existing downstream
operations were kept unchanged. Sixteen focused tests passed, but full real-input
comparison found Euler angle branch differences, so the candidate was removed
from the active implementation. Previously validated fitting and realtime mapping
changes remain intact.

Same saved inputs and same frozen fits; single measurements excluding loading:

| Dataset/model | Current seconds | Candidate seconds | Raw parity |
| --- | ---: | ---: | --- |
| Test human | 5.998 | 4.718 | 2 signed-pi angle differences |
| Test board | 0.218 | 0.148 | passed |
| Sample human | 30.117 | 24.055 | 6 signed-pi angle differences |
| Sample board | 1.088 | 0.599 | passed |

Only disagreements beyond rtol=1e-8/atol=1e-6 were joint-angle components at
+/-pi: test frame 194 left_index_metacarpal components 0/2; sample frames
962,963,964 right_index_metacarpal components 0/2. All compared positions,
quaternion components, masks, residuals, center of mass and other numeric outputs
passed. The differing angle values are within a few e-15 radians of the same
half-turn; equivalent orientations do not imply identical stored Euler numbers.
The tolerance was NOT widened and this checklist item is NOT complete.

Next decision: establish deterministic Euler branch-boundary representation in
the shared geometry implementation, or explicitly define circular-angle parity.
Do not silently call raw-value parity passed or introduce per-frame scalar
fallbacks that obscure the batching architecture. Full numerical mismatch paths
and timings: `.test-artifacts/batch-reconstruction/results.json`. Candidate code
and reproduction script are retained in that ignored diagnostic directory.

### Rotation comparison clarification

The batch experiment's eight raw Euler discrepancies at +/- pi are representation
wraps, not demonstrated orientation errors. Rotation comparisons now have a
reusable dataset diagnostic in `rotation_comparison.py`: validate unit wxyz
quaternions and missing masks, then measure the relative rotation angle using
SciPy. Equivalent q/-q quaternions must pass. Euler triples can be recomposed
using their declared intrinsic joint sequence and compared in rotation space;
this does not replace checking the joint definitions or clinical angle conventions
[@scipyRotationQuaternion; @scipyRotationEuler; @scipyRotationMagnitude].

These checks are test diagnostics, not extra runtime state. No angular-velocity
calculation was found in the current core or installed Forge Python sources.
The candidate batch implementation remains disabled pending application of these
checks to the complete recording comparison. No production rotation behavior or
numerical acceptance tolerance was changed in this step.

### 2026-10-13 — recording reconstruction batches enabled

Canonical output policy resolved the eight Euler endpoint disagreements. The
full saved test/sample reconstruction comparisons now report zero disagreements
(atol 1e-6, rtol 1e-8, same missing masks and dictionary coverage).

1. Map landmarks and recover independent geometry in chunks of 256 frames.
   Sequential roll state crosses chunk boundaries and resets on empty input
   exactly as before. Human reconstruction: test 4.239 -> 3.828 s; sample
   25.093 -> 20.516 s. Board: test .137 -> .111 s; sample .919 -> .594 s.
2. Compose the installed Forge AnchoredSkeletonGeometry, JointBatchGeometry,
   ResidualBatchGeometry and CenterOfMassGeometry APIs after roll resolution.
   Plans are prepared once per model/fit; arithmetic runs across frames and
   segments. Tree depth remains ordered; Python loops otherwise pack the public
   per-frame objects. No new cross-repository dependencies or math kernels.
   Additional isolated comparison: human test 4.087 -> 2.997 s; sample
   19.127 -> 14.400 s. Board test .115 -> .041 s; sample .543 -> .154 s.
   These are single-run pairs, not statistical estimates; do not combine the
   independently timed pairs to claim a measured total speedup.

Thirteen focused tests passed, including both tracker mappings, alternate anchors,
missing hands, empty observations, absent fits, and gaps spanning a chunk boundary.
The output assembly leaves the live scalar route in place; the post hoc route
uses recording batches. Existing Forge implementation provenance:
[@skellyforgeQuaternionMath2026].
