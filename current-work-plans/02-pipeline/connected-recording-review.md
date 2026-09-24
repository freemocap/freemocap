# Connected skeleton review on a saved recording

This is the next visual checkpoint after the synthetic SkellyForge viewer. It
uses the installed Forge through core's current reconstruction pipeline on saved
3D points. It does not run video detection, calibration or triangulation, and
does not publish reconstructed results back to the recording.

From the FreeMoCap repository, with its environment and existing UI dependencies:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tests.review_connected_recording "$HOME/freemocap_data/testing/prepared/freemocap_test_data/current/recordings/freemocap_test_data/freemocap_test_data_data.parquet" --output .test-artifacts/connected-recording-review.html
.\.venv\Scripts\python.exe -B -m http.server 8770 --bind 127.0.0.1 --directory .test-artifacts
```

Open http://127.0.0.1:8770/connected-recording-review.html. The self-contained HTML
can also be opened directly. Repeated generation overwrites this one disposable
artifact. Stop the server with Ctrl+C when finished.

The saved-data reader uses the recording's processing lock. Generation checks the
Parquet SHA256 before and after reading/reconstruction and includes source
revision, channel, units and installed dependency provenance in the artifact.

## What to inspect

- Yellow points: current landmark mapping of the saved 3D input.
- Orange segments: current core reconstruction's segment origins and rotations.
- Cyan segments: connected FK using the same rotations and the fitted rest
  offsets. Displacement from orange measures the representation difference,
  not ground-truth accuracy or a failed mathematical identity.
- RGB axes: selected segment orientation; inspect the neck, clavicles and limbs
  during motion and at nearly straight poses.

Playback starts paused in the last quarter. That is a convenient starting point,
not a certified clean interval. Inspect the board-occluded portion separately.
Timing uses saved timestamps. Missing poses and descendants with missing parents
are omitted; they are not filled with rest poses or interpolated.

The September 24 review has 222 frames. Body segment coverage is 214–216 frames
depending on the segment. This saved stream provides no reconstructed hand or
finger poses, so it cannot validate those on real data. Synthetic hand checks
remain separate. The viewer displays coverage per segment.

## Validation and next handoff

Latest viewer regenerated with SkellyForge `fa4808b55fbc8885a1420b340b3606f5516b5bed`
(explicit pelvis/thorax observation frames). Core's installed package and lockfile
match the pushed revision. All 222 saved frames were reused, with unchanged source
checksum. Direct inspection of the generated data confirmed the pelvis and thorax
X axes follow their respective hip/shoulder lines in all 216 available poses each.
The three boundary unit tests pass. This checks the geometric contract, not
anatomical accuracy. Visual review precedes the linked spine/clavicle solver.

### Shoulder attachment inspection

Click **Focus shoulders** to frame the shoulder region and hide the general
landmark, independent-segment and axis overlays. White labeled markers show the
saved left/right shoulder keypoints and their derived midpoint. Magenta markers
show mapped sternoclavicular (SC) joints; cyan markers show connected clavicle
origins. Each layer and the labels can be toggled independently. Magenta lines
connect corresponding SC estimates. The panel reports gaps and bilateral widths
in millimeters, plus the midpoint-to-connected-neck distance. Missing points
remain unavailable. The saved keypoint channel may already be filtered.

The shoulder mapping defines SC offsets as fractions of observed shoulder width;
the connected hierarchy defines them in thoracic template coordinates scaled by
the fitted thoracic scale. Thus they are not currently the same construction.
Changing thoracic scale alone also changes transverse and anterior attachments.
Inspect this disagreement before implementing flexible spine spans. This viewer
does not modify either attachment definition or fit a new torso model.

### Recheck after symmetric tracker attachments

Installed SkellyTracker, core lockfile, dependency checkout and remote branch
were verified at `51c9934d371cfad231e72744fce4cc3a43befb9f`. Regenerating all
222 frames preserved the source Parquet checksum. On sample indices 166–221,
RMS position disagreement changed as follows (millimeters):

| Comparison | Before | After |
| --- | ---: | ---: |
| Mapped versus connected left/right SC | 39.0 | 40.5 |
| Reconstructed versus connected left upper-arm origin | 40.7 | 42.0 |
| Reconstructed versus connected right upper-arm origin | 40.4 | 41.5 |
| Reconstructed versus connected thoracic origin | 37.5 | 41.3 |
| Reconstructed versus connected cervical origin | 56.2 | 38.0 |

Coverage was unchanged. These are representation differences, not anatomical
accuracy measurements. Correcting asymmetric/inconsistent reference offsets
improved neck agreement but did not resolve shoulder disagreement. The tracker
still estimates attachments from observed shoulder width, whereas connected FK
uses frozen thoracic dimensions. Next isolate fixed spine span effects from
torso pose fitting before introducing flexibility. The overwritten diagnostic
report `.test-artifacts/shoulder-mapping-comparison.json` retains both package
provenances and measurements; it is not a recording product.

```powershell
.\.venv\Scripts\python.exe -B -m unittest freemocap.tests.test_connected_recording_review -v
```

These boundary checks cover exact rest-pose FK and omission of missing/nonfinite
poses with ancestor closure. They do not certify anatomical reconstruction.
The existing pytest hierarchy suite still needs running in an environment with
pytest; it was unavailable in core's current environment during this checkpoint.

After visual review and core commit/push, choose a usable real-data interval and
an explicit missing-data policy for the first BVH/GLB round-trip. The next feature
chunk should prepare a shared animation hierarchy, then verify exported/imported
world transforms against that hierarchy. Do not demand that its fixed offsets
exactly reproduce noisy landmark trajectories. No exporter or anatomical IK
solver is implemented by this review tool.
