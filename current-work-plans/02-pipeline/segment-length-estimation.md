# Segment Length Estimation

**Describes:** how segment lengths adapt from the authored seed to the live subject —
skellyforge's `estimate_segment_lengths` (`core/skeleton/pose/segment_length_estimation.py`) and
freemocap's streaming adaptation of it in the aggregator.

## The skellyforge function

Stateless and pure: `estimate_segment_lengths(segments=..., observed=...) -> dict[str, float]`
returns, per measurable segment, the **median** of frame-wise origin→primary-direction distances
across the observed frames; `measurable_segments(...)` names what qualifies. It raises
`ValueError` when a segment's origin or primary landmark is missing — no fallback, no
interpolation, fail loud. There is no window state inside skellyforge: any windowing is the
caller's job.

## Where it runs today (realtime — wired)

The aggregator keeps a per-segment rolling deque (`LENGTH_WINDOW_FRAMES = 30`) of observed
origin→primary distances. Each frame after roll resolution, every segment with BOTH landmarks
hydrated and finite contributes its distance; published `SEGMENT_LENGTHS` are the **median over
the window**, falling back to each segment's authored rest-pose length until measurements exist.
The window clears on calibration hot-reload / skeleton-fit reset. This is an inline streaming
adaptation of the same median idea (tolerating partial hydration frame-to-frame), not a call into
skellyforge's batch function.

Posthoc parity note: batch posthoc uses the full-recording window (unbounded) once the posthoc
rebuild lands ([posthoc-rebuild.md](posthoc-rebuild.md)).

## Cleanup owed

- `realtime_filter_config.segment_length_window_s` is a dead field (defined, never read) — delete
  it or make it drive `LENGTH_WINDOW_FRAMES`; one decision point, not two.
- Decide whether the aggregator should call skellyforge's estimator directly (over a buffered
  observation window) instead of mirroring it inline — one implementation of the median rule,
  not two.
