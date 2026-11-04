# Windows integration validation

Canonical Core `sfn26` at `142f73eb`, with the scoped fixes described below, was
tested on Windows 11, i9-12900KF, RTX 3090 and 127.796 GiB RAM. Each record retains
actual editable sources and dirty-source fingerprints. Unrelated bootstrap sources
and bibliography edits were preserved. This was a shared desktop, not an idle trial.

## Standard reference result

The corrected standard `test_data` run passed: 222 synchronized frames, 666 camera
images, fresh calibration, RTMW/YOLOX with logged CUDAExecutionProvider and CPU
fallback. NPZ, wide CSV, notebook and Blender files exist. Blender scene reopening
validation passed; the automatic GUI loaded the final promoted path, exercised its
event loop, quit gracefully and exited with code 0. Independent process inspection
confirmed no test-owned Blender or Python worker remained. The dataset worker defers GUI opening to its parent
workflow; its recorded `auto_open_blend_file=false` is not a disabled workflow export.

| Span | Seconds | ms/synchronized frame | frames/s |
|---|---:|---:|---:|
| Wrapper, including promotion, GUI launch and quit | 68.0580 | 306.568 | 3.262 |
| Worker, including calibration and validation | 56.0108 | 252.301 | 3.964 |
| Posthoc processing | 29.5254 | 132.997 | 7.519 |
| Inference calls, three images per call | 7.61392 | 34.2969 | 29.157 |

Inference amortized cost was 11.4323 ms/image (87.471 images/s); first call 79.2365 ms,
after-first mean 34.0936 ms, maximum 79.2365 ms. Session setup was 1.33511 seconds.
These overlapping spans must not be added. Rates are recording-processing rates,
not live display FPS. There is **one observation of the final bounded GUI lifecycle**, not a
stable regression baseline. An earlier successful run before the teardown requirement
left Blender open: 63.0531 wrapper seconds, 55.3011 worker seconds, 35.1563 ms per
inference batch, with a short browser test overlapping startup. It remains separately
archived and is not pooled with the final lifecycle measurement.
No sample-data repetition, full reference matrix or frozen application was run.

The [successful record](results/2026-11-04-windows-rtx3090-standard-lifecycle-test-01.json)
and [full timing table](results/2026-11-04-windows-rtx3090-standard-lifecycle-test-01.md)
retain all measured values. Historical Mac runs are not controlled paired trials.

## Defects and retained failed attempts

- Two output locations were rejected before processing by Windows MAX_PATH checks.
  Both failed preflight records are retained; a short external temporary root worked.
- Auto-open inherited the worker's captured output handles. The worker exited, but
  its log reader could not finish while Blender remained open. Gracefully closing
  only that benchmark-created GUI released the wrapper. The intervened observation
  reports 164.931 seconds and is **excluded from performance comparisons**.
- Giving the GUI independent standard handles fixed that wait, then exposed a
  Windows directory lock: opening the candidate before promotion prevented rename.
  That failed observation retains 78.4631 worker seconds and completed stage evidence;
  it is not a successful workflow result.
- Standard processing now exports and validates in the worker and opens the final
  promoted scene afterward. Ordinary application auto-open also uses independent
  handles. Export settings and validation criteria were not weakened.

## Focused checks and UI limitations

- 44 backend benchmark/progress/performance checks pass across the original run
  and the 12-test benchmark rerun after two test-portability fixes.
- 25 Blender export/preparation tests and 32 workflow tests pass. Workflow temporary
  roots must also be short on Windows. Ruff and whitespace checks pass.
- Rebuilding the existing local SDK resolves stale ignored build outputs after the
  pull. UI typecheck and SDK integration pass: 120 tests plus one existing recording
  fixture skip, and nine operation-progress tests. Three browser progress checks pass.
- The source style checker previously used Windows backslashes in Git object paths
  and missed its color-file exemption. Normalizing relative paths restores **44 real
  findings**, down from 243 spurious/real combined findings. Its exit remains failure.
- The user-authorized dependency refresh by the SDK owner installed the declared
  accessibility package without manifest/lock changes. The requested bundled browser
  was absent; the existing Edge channel ran the modal visual harness instead.
  It failed eight screenshot comparisons (14,309–22,438 differing pixels). The
  request fixture's obsolete `exportToBlender=false` expectation was corrected to
  the enabled export contract; the rerun passes that assertion but retains eight
  visual failures and seven contrast-node findings across five sections. Screenshot
  baselines and tolerances were not changed. Other four
  harness tests/main surfaces were not run. Cross-browser rendering is a confounder.
- Older operations missing `items` are rejected by the current SDK; current backend
  snapshots contain it. The owner explicitly chose no backward compatibility at
  this stage, so no compatibility shim was added. Separate per-video bars remain
  outstanding. DLC remains partially supported with deferred compatibility gaps;
  no DLC acceptance is claimed.

Local detailed evidence is in `.test-artifacts/benchmarks/windows-20261104`,
`.test-artifacts/harness-results`, and the short external benchmark output roots.
Only reviewed small records are archived here; bulk recordings/logs remain local.

## Physical cameras

The existing quick suite ran sequentially on Python and Rust, four available cameras,
1280×720 at requested 30 FPS with the suite's resolution/control transitions.
It took 412.904 seconds: **31 of 32 cases passed** (Python 15/16, Rust 16/16).
Recording with one, two, three and four cameras passed on both backends. This is
quick-suite coverage, not every physical subset or the extended matrix.

Python `close-during-recording` failed the unchanged rate criterion: four camera
rates were 29.519–29.524 FPS, outside ±1% of 30 FPS. Each saved video had 121 decoded
frames, matching capture timestamps/indices, and zero missing frame numbers.
The assertion text says "incomplete recording", but the measured failure is rate,
not missing frames. No camera implementation fix or relaxed tolerance is claimed.
Both isolated servers report exit code 0 and no cleanup errors; an independent
process inspection confirmed their workers exited and cameras were released.
The [camera record](results/2026-11-04-windows-rtx3090-cameras-quick-01.json)
retains failed evidence alongside successful measurements.
