# Trajectory completion and complete skeletons

## FreeMoCap stage implemented

One named 100 ms threshold governs trajectory cleanup. Gaps whose bracketing
valid timestamps are at most 100 ms apart join neighboring detections before
support is assessed. Consecutive valid samples form a run at any frame rate.
Runs need at least two samples and at least 100 ms from first to last sample.
Discarded detections cannot anchor interpolation or endpoint extension. Surviving
tracks are completed over the recording; tracks with no surviving support are
left for parent-relative model completion, not passed as partial filter runs.
The report stores discarded as well as filled spans; original raw support can
be reconstructed independently from retained measurement support.

The post-hoc mocap task now calls `prepare_recording_points`: timestamp-linear
interior gap filling, nearest-valid endpoint extension, then the existing
Butterworth filter. Gap filling also runs when smoothing is disabled. Original
triangulated points remain in RAW_KEYPOINTS_3D. Prepared positions are saved in
KEYPOINTS_3D and used for reconstruction.

The filtering report stores filled index spans and entirely unsupported track
indices. Indices refer to the saved frame/keypoint grid, not camera frame IDs.
Scale fitting excludes filled samples. Alignment uses filtered positions only
at originally measured samples, retaining reprojection-quality gating. Both
completed positions and raw positions receive the same alignment transform.
Publication verifies provenance against raw support; saved reconstruction
restores that support when validating the scale-fit input signature.

Validation: 48 focused filtering, alignment, scale, gap-fill and Parquet reload
tests passed, with existing dependency deprecation warnings. An in-memory run
on the actual 1108-frame sample RAW_KEYPOINTS_3D stream produced 225 complete
tracks, zero unsupported tracks, 85966 filled samples and 199 discarded
detections. No partial keypoint track reaches Butterworth. No saved recording
or solver comparison was overwritten. Existing preparation-script and uv.lock
edits were present before this work and were not changed.

After the human commits this FreeMoCap stage, regenerate the sample with person
alignment enabled, then rerun the same skeleton comparison settings against
that prepared input. Compare geometry as well as residuals before adding more
solver constraints. Runtime prediction remains a separate future change.


## Required next stage: SkellyForge

This is not yet the complete requested behavior. Never-observed keypoint tracks
remain unsupported in the measurement stream; the corresponding model parts
must be completed with person-scaled authored rest geometry relative to their
fitted parents. This is the approved behavior, not an optional omission policy.
An untracked hand must follow the wrist with its rest finger configuration.

Current hydration/reconstruction skips unsupported segments. Extend the existing
quaternion/rest-pose/attachment machinery in Forge to complete these parts,
retain explicit fallback provenance, and keep their orientations fixed relative
to the parent during the experimental Ceres solve instead of adding free
unsupported parameters. Do not create fake keypoint measurement residuals.
Test moving-parent/untracked-child behavior, full landmark output, unchanged
tracked poses, and correct person scale. Then integrate via the human-owned
dependency handoff and regenerate the prepared sample and viewer fits.

The entire-model-with-no-observation/no-scale case still needs an explicit world
placement and scale policy; it must not be confused with an untracked child of
an otherwise fitted skeleton. No default world placement was introduced here.
