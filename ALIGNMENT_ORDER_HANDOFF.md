# Filter before person / ground alignment

The posthoc pipeline previously estimated foot contact from unfiltered triangulated
keypoints, then ran Butterworth filtering. That ordering prevented the filter from
helping contact detection. It now triangulates, filters trajectories, estimates
alignment from the filtered trajectories, applies the same rigid transform to raw
points, filtered points, and cameras, then reconstructs the skeleton.

`MocapAlignmentRequest.filtered_points` is explicit and required. Shape and missing
keypoint support must match raw triangulation. Reprojection errors and positive-depth
quality checks still use the original triangulation, not smoothed evidence.
Raw and filtered recording channels remain separate and share one aligned frame.

No contact thresholds or Forge contact estimator changes are required for this fix.
The uncommitted dwell-regression estimator experiment and its exclusive tests/fixture
were removed from SkellyForge; the committed original estimator was restored on disk
without changing Git state. Existing Ceres and other user work is preserved.

Sample evidence replay using FreeMoCap's installed original Forge estimator and
the standard 6 Hz fourth-order Butterworth filter returned:

- `foot_support`, 15 contact episodes;
- plane support 1.0;
- plane RMS residual 3.7753 mm;
- 599 filtered trajectory runs, 1073 preserved short runs.

Replay script/log: workspace `repos/_alignment-investigation/alignment_filtered_replay.*`.
It reads the saved sample, undoes its old person transform, restores the recorded
mapping/model and calibration, filters, then invokes the modified alignment entry
point. It does not regenerate or modify prepared recording files.

Validation: 40 core alignment/filtering/recording/scale tests passed, including a
new regression checking that filtered positions drive alignment while raw positions
and reprojection evidence remain distinct and both outputs receive the same transform.
The restored Forge alignment suite passes 18 tests.

Commit/push the three changed core code/test files and this report on
`development-streaming`, preserving unrelated existing changes. No Forge dependency
refresh is needed for this correction. Full posthoc regeneration and playback review
remain to be performed, followed by rebuilding downstream sample Ceres fits from the
new Parquet. Existing cached fits and prepared outputs still use the old alignment.
