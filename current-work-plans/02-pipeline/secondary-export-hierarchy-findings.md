# Saved hierarchy evidence for secondary exports

## Recheck after mapping correction — 2026-09-24

The installed Tracker includes the four-keypoint chest midpoint correction.
Reused the exact saved 3D inputs and reran only production scale fitting and
skeleton reconstruction with current installed definitions. No calibration,
detector inference, or Parquet publication occurred; source hash stayed unchanged.
Full results and installed package revisions: [recheck JSON](secondary-export-hierarchy-recheck.json).

| Segment | Previous fitted-rest FK RMS (mm) | Current fitted-rest FK RMS (mm) |
| --- | ---: | ---: |
| Thoracic | 241.16 | 41.54 |
| Cervical spine | 229.84 | 60.74 |
| Left lower arm | 242.61 | 47.80 |
| Right lower arm | 243.07 | 50.35 |

The large static mismatch substantially decreased. Mean-observed-offset FK RMS
remained unchanged for these links (thoracic 36.27 mm). This comparison is not
an optimized connected-armature fit or a clean-motion-only quality assessment.
The remaining errors do not establish an export limitation. No new tests were
added for this recheck. Reproduce with the diagnostic command below plus
`--reconstruct-current`, writing to the recheck JSON rather than the original report.

## Original measurement

Measured 2026-09-23 using existing prepared test Parquet, without video access,
calibration lookup, inference, or reconstruction. Source SHA-256 was identical
before and after inspection. Core checkout: `00a37b73d622becb92862917c56a47d1f6e2c4aa`.
Installed SkellyForge: `9e6ed96f52e3dedba0a0836aa918130fc65bb254`; no dependencies
were refreshed for this investigation.
Full per-edge results and source identity: [JSON report](secondary-export-hierarchy-report.json).
This is evidence for the [export proposal](secondary-exports.md), not an exporter
implementation or approval of its format defaults.

## Result

Retaining recorded orientations and time-varying parent-local translations
reproduces the saved transforms. A fixed-offset hierarchy does not reproduce
these saved positions with those same orientations.

The selected saved human model has 61 segments over 222 frames (0–36.8333 s).
Only 20 of its 60 parent-child links have usable complete ancestor paths. The
remaining 40 have no FK evidence; zero samples are reported as null error, not
perfect agreement. Observed links typically have 214–216 usable frames.

Exact local-transform reconstruction has maximum position error **1.62e-12 mm**
(rounded upward) and maximum rotation-matrix Frobenius error **3.87e-15**.
This establishes mathematical parity with stored samples, not anatomical accuracy.

| Segment | Fitted-rest FK RMS error (mm) | Mean-offset FK RMS error (mm) |
| --- | ---: | ---: |
| Thoracic | 241.16 | 36.27 |
| Left lower arm | 242.61 | 40.37 |
| Right lower arm | 243.07 | 42.93 |
| Right toes | 46.04 | 45.59 |

The thoracic attachment illustrates both a static mismatch and temporal variation:
its fitted-rest offset is approximately `(0, 0, 530.74)` mm, while the mean observed
offset is `(0.02, -0.06, 292.32)` mm. Its variation around that mean has 36.27 mm RMS
and 136.70 mm maximum magnitude. This merits a separate rest-definition/scale-fit
investigation before presenting a conventional fitted rig as equivalent to playback.
This diagnostic does not establish the cause or modify either definition or fit.

## Method and limits

- Descriptor and scalar samples come from one open Parquet snapshot. Selection
  includes run, model source, sensor group, reference frame, and explicit units.
  Ambiguous groups, duplicate scalar samples, and incompatible contexts fail.
- Restore the embedded skeleton/rest pose; use the saved fitted scales, without
  recomputing them. Positions are already aligned; no alignment is reapplied.
- For each observed child, compute `R_local = R_parent.T @ R_child` and
  `p_local = R_parent.T @ (p_child - p_parent)`.
- Compose local rotations and translations along the hierarchy, retaining the
  recorded moving root. Missing required ancestors invalidate descendant FK.
- Compare two constant translation choices: the stored parent-owned `connect_at`
  landmark times the parent's fitted scale, and the mean observed parent-local
  translation. The first follows the saved rest hierarchy's attachment convention;
  it is not inferred from segment lengths alone.
- Mean offsets minimize each edge's squared translation residual on its observed
  samples. They do not minimize whole-hierarchy FK error, use held-out evaluation,
  or constitute a new rig-fitting algorithm. No alternate orientations/IK are fitted.
- RMS/p95/max are over available samples per link, with counts alongside them.
  This is one decimated recording, not a motion-quality or timing benchmark.

## Consequence for export work

For faithful playback, preserve animated local translations or independent world
transforms. For a conventional fixed-offset rig, explicitly accept and quantify
approximation or implement a separately validated fitting step. Importer support
and visual parity still need testing when actual BVH/glTF writers exist.
CSV/NumPy can preserve the existing numerical samples without choosing either rig
profile. Missing-data policy remains explicit future work.

## Reproduce

From the core checkout, with its existing environment:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tests.inspect_export_hierarchy "$HOME/freemocap_data/testing/prepared/freemocap_test_data/current/recordings/freemocap_test_data/freemocap_test_data_data.parquet" --output current-work-plans/02-pipeline/secondary-export-hierarchy-report.json
.\.venv\Scripts\python.exe -B -m pytest freemocap/tests/test_export_hierarchy.py -q
```

The command requires an existing file and never prepares missing data. The real-data
test skips explicitly if it is absent. Six tests passed, including known analytic
errors, branching/moving-root composition, missing ancestor propagation, entirely
absent evidence, invalid parent maps, and read-only inspection of the actual file.
Approximation errors are measured rather than pinned as required failures, allowing
future reconstruction improvements. Ruff passed on both new Python modules.
