# Computational Benchy bootstrapping

The controller must run from a configuration file and persisted state. No language
model, browser session, manual point labels, or visual acceptance decision is a
required transition. Human visual observations are supplementary evidence only.

## Ownership and established workflow

Core coordinates command execution across repositories. Tracker owns inference,
frame selection, dense training arrays, DLC training, evaluation and versioned
storage. Forge owns calibrated geometry fitting and label-support tests. The
repositories exchange explicit files; Tracker and Forge do not import each other.

DLC describes an iterative workflow of identifying poor predictions, refining
their labels, merging examples and retraining. It offers confidence/jump-based
outlier detection and diversity sampling. Its documented correction step uses
human review; this experiment substitutes computational geometry checks. That
substitution is our design, not a claim that DLC guarantees automatic labels.
[@dlcIterativeRefinement]

## Fixed experiment rules

- Start from the accepted two-stage epoch-120 checkpoint and accumulated dataset.
- Run at most three rounds, each adding at most 40 qualified camera images.
  The original 120-additional-epoch budget applied to rounds one and two;
  the approved adaptive amendment below governs the extension and round three.
  Preserve older examples and versions.
- Keep development frames and the entire reserved challenge interval out of
  mining and training, including the existing temporal guards.
- Select both easy and difficult predictions with temporal/appearance diversity.
  A bad prediction identifies a candidate; it does not establish a bad label.
- Generate labels from a shared calibrated pose followed by bounded per-camera
  refinement. Record silhouette support, pose ambiguity, visibility, camera
  agreement and every exclusion reason with numeric evidence.
- Quarantine unsupported labels in the next dataset version; never erase source
  images or historical labels. Do not lower thresholds merely to fill a quota.
- Continue saved training state; record checkpoint identity, actual starting and
  ending epochs, optimizer steps, scheduler state and dataset hashes.
- Rank completed models using mean error on the same unfiltered development
  references. Retain the previous model unless improvement exceeds a fixed
  0.05 native-pixel margin; confidence-filtered metrics are supporting evidence.
- Stop on the round limit, insufficient qualified new data, invalid geometry,
  nonfinite training/evaluation, or failed integrity checks. Stop reasons are
  machine-readable records, not unwritten judgments.

## Persistence and recovery

All experiment data lives outside source checkouts. `bootstrap_controller.py`
executes an explicit command list, saves running/completed/failed stage records
atomically, and verifies the completion-file hash before skipping a finished
stage. Failed or interrupted stages require a named new attempt; partial output
must never be mistaken for a completed artifact. It does not choose scientific
parameters. Dataset manifests and domain-owned validation provide those contracts.

## Limits to preserve in every report

The development references are automatic shared-fit projections, not independent
ground truth. Repeated model selection makes this a development benchmark, not a
blind final test. Per-camera refinement can improve image alignment while losing
exact multiview consistency; shared-pose and per-camera evidence stay separate.
Confidence is not accuracy. Do not delete difficult examples just because model
loss is high. No automatic method here guarantees removal of every bad label.

Record implementation choices, thresholds, exceptions and measured outcomes in
the experiment's external decision records as the implementation develops. Any
manual intervention must identify why the deterministic controller could not act.

## Executable label decisions

`skellyforge/tools/stl_training/bootstrap_geometry.py` requires at least three
usable camera masks. A shared pose must have three silhouette IoUs of at least
0.55. A camera is an outlier when its IoU is below the median minus the larger
of 0.15 and 2.5 times the scaled median absolute deviation. One trim/refit is
allowed; a failed refit rejects the candidate rather than relaxing the rule.

Competing shared fits with a score margin below 0.03 and a 95th-percentile
projection difference above eight native pixels reject that camera's labels.
Each retained keypoint must have positive depth, lie inside the image, be visible
against the mesh depth within two millimeters, and lie within three native pixels
of the yellow foreground mask. Per-camera refinement preserves these conditions
and must improve silhouette overlap. Its bounds are 0.20 radians per rotation
component, four millimeters per translation component, and twelve projected
pixels. The original shared fit remains the fallback.

Existing training labels receive a fresh foreground-support audit; their earlier
pose-fit evidence is retained, not recomputed. This is not full retrospective
pose re-estimation or an Anipose implementation. Removed points are quarantined
in the next version's validity tensor, with counts and reasons. Development
coordinates and masks are protected by assertions.

Tracker's `merge_bootstrap_labels.py` requires eight qualified points per new
image. It alternates reliable/failure groups, visits distinct frame times before
adding additional cameras at those times, and caps additions at forty images.
Fewer than four qualified images produces a recorded stop. Every candidate has
an acceptance, geometry-rejection, or budget-exclusion reason. These fixed rules
are intentionally conservative experimental choices, not universal constants.

## Training duration and approved adaptive amendment

The original three-round plan used 120 **additional** epochs per round.
It resumed model, optimizer and scheduler state rather than restarting training
from scratch. That bound did not establish convergence.
DLC's PyTorch guide recommends training until loss plateaus, often around
100–250 epochs, and illustrates 200 epochs. Older TensorFlow iteration counts
are not comparable to epoch counts. [@dlcIterativeRefinement]

After each dataset expansion, the effective training problem changes. A large
cumulative epoch count alone does not show that the new examples have been
learned sufficiently. After the first two bounded rounds, the owner approved an
adaptive extension of round two and adaptive training for round three:

- Evaluate mean native-pixel error on the unchanged 227 development references
  every 20 additional epochs, with no confidence filtering for the stop decision.
- Compare against the most recent meaningful-improvement anchor. An improvement
  of at least 0.05 pixels resets that anchor and the patience counter. Several
  smaller improvements can accumulate to meet this threshold.
- Stop after 60 epochs without such improvement, or 300 additional epochs,
  whichever occurs first. These settings are in `adaptive-policy.json`.
- Track the lowest measured error separately, and retain that checkpoint even
  when the final checkpoint is worse. Save every validation result and decision.
- Keep training continuous within the adaptive run: validation happens in a
  separate inference process after a saved checkpoint. Training RNG, optimizer
  and scheduler state are not reset at each 20-epoch check.

`run_adaptive_bootstrap.py` implements the approved transition. Original round
two remains intact; its extension has a separate directory and uses the same
dataset. Round-three candidate mining had already completed using epoch 360
when the amendment was approved; those candidates and their independent
geometry labels retain that provenance. Round-three training starts from the
retained extension model. The existing learning-rate schedule is preserved;
changing or restarting it would be a separate recorded intervention.

## Reproduce or resume this experiment

The external `controller-config.json` records exact interpreter, source and
artifact paths. Run `run_adaptive_bootstrap.py --config <that file>` using the
recorded Python executable. Completed stage records are validated and skipped.
An interrupted or failed stage stops rather than guessing how to reuse partial
outputs. Its explicit recovery requires a new attempt record or validated
completion, with the reason recorded. This is an error-recovery boundary, not
a requirement for AI orchestration during ordinary rounds.

The experiment remains specific to this calibrated yellow-object recording:
foreground-mask thresholds, STL geometry, camera identities and evaluation
intervals are configured for it. Generalizing input discovery and foreground
segmentation is separate from demonstrating a computational training loop.
