---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Geometry matcher audit — 2026-09-10

Scope: matching input assembly, sampling, scoring, assignment search, result application, lifecycle, and existing tests. This is a review, not acceptance of the matcher for live calibration decisions.

## Confirmed findings

1. **Point selection is unjustified.** `observation_sampling.py:select_matching_point_names` still caps the selection at 64. The interrupted confidence-ranking edit does not resolve the fundamental issue. The live adapter previously took the first 64 flattened names, with skeleton stages preceding ChArUco. This makes detector ordering affect which geometry is checked. No measured resource requirement or representative accuracy test establishes this cap.
2. **Live evidence depends on the initial sample.** `live_matching.py:update` creates its layout once, when `_window is None`. Later point names cannot enter the window. The confidence-ranking edit makes the initial visibility state another selection dependency. Board points appearing later can remain excluded.
3. **Evidence quality and calibration quality are conflated.** The adapter supplied all positive-confidence detections; runtime detection thresholds are as low as 0.0025. The fitness evaluator requires every camera to pass median, p90, and valid-fraction thresholds. Incorrect correspondences, occlusion, and uncertain detections can therefore yield `poor` with correct camera geometry. The proposed 0.5 visibility threshold is not yet validated against actual detector score distributions.
4. **Rejection can still reset reconstruction state.** `live_matching.py:update` sets `changed` when a result has an assignment and a search, regardless of whether it was accepted. `realtime_aggregator_node.py` uses that flag to reset keypoint filtering, point gating, and skeleton fitting. Retaining the binding under continue policy alone does not remove this side effect.
5. **A rejection suspends subsequent evaluation.** `matching_lifecycle.py:finish` enters SUSPENDED for poor/ambiguous/search-limit results. The live caller then ignores fresh observations until configuration or calibration generation resets matching. Better visibility alone cannot recover the check.
6. **The tests do not reproduce the reported evidence.** `test_posthoc_matching.py:recorded_request` constructs observations from synthetic projections, using ten points with visibility 1.0. These tests are useful for geometric bookkeeping but do not exercise a full mixed body/face/hand/board stream, startup visibility changes, or detector uncertainty. The audited suite passes 34 tests despite the issues above.
7. **The supplied incident log cannot identify the numerical cause.** It records `poor`, without the sampled names, original-assignment per-camera diagnostics, or input observations. The added diagnostic logging is a partial improvement; retaining diagnostics for the initial binding separately from a searched candidate is still needed. The 64-point cap is a confirmed defect, not proof that it alone caused this incident.

## Limits requiring explicit rationale

- `max(24, minimum_frames * 2)` and a 0.2-second sampling interval define the observation window. The factor of two supports separate search/validation subsets; the 24-frame floor needs its own rationale.
- Alternating frames provide a held-out subset, but nearby temporally filtered detector outputs are correlated. This is not independent evidence that a candidate is correct.
- The 250,000-node search limit is an explicit combinatorial resource budget that reports SEARCH_LIMIT. It serves a different purpose from silently dropping point names.
- Errors are measured in pixels normalized to a 1000-pixel image diagonal. The current median/p90 limits need validation against real detector observations, not just exact synthetic projections. No unit-conversion defect was established in this review.

## Required acceptance evidence before algorithm changes are called complete

- Use all qualified named observations, without detector-order-dependent truncation; include names that appear after startup.
- Separate inadequate or unreliable observations from a camera-assignment mismatch, and preserve the original assignment's diagnostic evidence.
- Make result application transactional: only an accepted, changed assignment can trigger reconstruction resets.
- Specify recovery behavior when fresh evidence arrives after a rejected check.
- Replay actual observations with a known calibration, alongside deliberately permuted cameras, poor tracking, occlusion, and mixed detector stages. Check both false rejection and false acceptance.
- Measure matching cost on representative full point sets before introducing any sampling optimization.

The confidence-selection edits from the interrupted turn remain in the working tree. They are provisional and are not endorsed by this audit. No further algorithm changes were made during this review, and the reported recording has not been replayed.
