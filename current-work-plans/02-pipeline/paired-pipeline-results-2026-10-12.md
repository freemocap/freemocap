# Matched existing-pipeline versus graph measurements

Both implementations independently processed all camera images on both reference
recordings. Both used the same calibration snapshot, RTMW-x-l 256x192, confidence
threshold 0.4, ChArUco, annotation, filtering settings and Blender exports. Source
identities and scientific/export configuration were compared before numerical
acceptance. All four runs registered CUDA as their first execution provider.
The existing path requested TensorRT and fell back to CUDA; the graph requested
CUDA directly. These measurements use the currently installed dependencies on
both paths, not a checkout of an older historical revision.

| Recording | Motion frames | Existing pipeline | New graph | Time reduction | Existing ms/frame | Graph ms/frame |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Test | 222 | 37.530 s | 32.629 s | 13.1% | 169.05 | 146.98 |
| Sample | 1,108 | 135.953 s | 112.250 s | 17.4% | 122.70 | 101.31 |

One motion frame includes all three camera views. Timings include loading,
tracking, annotation, reconstruction, saves and Blender export. They exclude
fresh calibration solving and the reference runner's extra output validation.
Neither run requested CSV/NPY/NPZ; both used the same standard output profile.
Complete worker lifecycle including startup and validation was 51.054 / 46.107 s
for test and 163.672 / 140.824 s for sample (existing / graph).
These are single paired observations in fixed existing-then-graph order, not
statistical speedup estimates or a real-time inference benchmark.

## Numerical results

**Both recordings passed all 36 saved-channel comparisons. Maximum numerical
difference: zero.** Missing-value masks, frame numbers, timestamps, channel
definitions, scientific models, coordinate frames, camera geometry and scale-fit
definitions also passed. Each local fit fingerprint was checked against its own
saved inputs. Both output sets passed standard Parquet and saved-Blender validation.

The comparator initially treated two `ModelScaleFit` frozenset fields as ordered
JSON lists. Separate interpreter hash seeds produced different serialization
orders. Comparison now checks their membership without changing ordered axes or
numerical tolerances. Existing tolerance remains absolute 1e-6 / relative 1e-8;
no tolerance increase was needed. Output comparisons were rerun after this fix
without rerunning or changing the measured outputs.

## Where time changed

| Operation | Test existing / graph | Sample existing / graph |
| --- | ---: | ---: |
| Loading and tracking interval | 18.150 / 10.627 s | 80.523 / 47.650 s |
| Existing coordinator annotation wait | 10.263 s | 49.187 s |
| Export interval | 10.118 / 10.152 s | 13.178 / 13.091 s |

The existing loading/tracking interval includes its annotation waits. The graph
annotation handlers run separately and overlap numerical processing. Their work
still contributes to full completion, so the load/track saving is larger than the
whole-pipeline saving. Overlapping stage rows must not be added. The graph remains
far from a full-pipeline 30 motion-frame/s target; this comparison establishes a
measured improvement with identical numerical output, not completion of optimization.

## Reproduce and inspect

From the core repository, use its existing environment:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tools.datasets.pipeline_comparison --output C:/Users/jonma/freemocap_data/testing/ab-next
```

The output directory must not exist. Use a short path outside source/prepared
roots. It calls the existing reference workflow with `--implementation current`
and `--implementation graph`, preserves both output sets and writes
`comparison.json` plus `comparison.txt`. Each run keeps its request, log and
validation evidence. Graph saved-stage starts still fail explicitly.

This measurement is saved under `C:/Users/jonma/freemocap_data/testing/ab/`.
Console logs are in `.test-artifacts/pipeline-comparison.txt`; the corrected
comparison evidence is in `.test-artifacts/comparison-recheck.txt` and the final
`ab/comparison.json`. Selection/workflow regression checks: 35 tests plus four
subtests passed. No Git-state changes were performed.
