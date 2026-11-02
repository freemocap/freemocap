"""Represent immutable SkellyCam acquisition instants on the local LSL clock.

Both clocks are monotonic. The calibration observes their relative origins; it
does not timestamp a measurement. Conversion always uses the supplied acquisition
timestamp, even if inference, queueing or delivery takes arbitrarily long.
[@lslTimeSynchronizationGuide]
"""
from __future__ import annotations

from collections.abc import Callable  # noqa: TC003 - runtime beartype resolution
from dataclasses import dataclass
import math
import time


@dataclass(frozen=True, slots=True)
class LslClockMapping:
    """One local clock-domain anchor, with the observed calibration interval.

    Keep the integer nanosecond anchor so nearby integer acquisition instants are
    subtracted before conversion to LSL's floating-point seconds. Original camera
    timestamps remain separate immutable provenance; this representation is not a
    replacement for them. This anchor does not map a previous machine/boot's clock.
    """

    perf_counter_anchor_ns: int
    lsl_anchor_s: float
    calibration_span_ns: int = 0

    def __post_init__(self) -> None:
        if self.perf_counter_anchor_ns < 0 or self.calibration_span_ns < 0:
            raise ValueError('Clock anchor and calibration interval must be nonnegative')
        if not math.isfinite(self.lsl_anchor_s):
            raise ValueError('LSL clock anchor must be finite')

    def to_lsl_seconds(self, capture_timestamp_ns: int | float) -> float:
        """Express the same acquisition instant in seconds on the local LSL clock."""
        if isinstance(capture_timestamp_ns, bool) or not math.isfinite(capture_timestamp_ns):
            raise ValueError('Acquisition timestamp must be a finite number of nanoseconds')
        if capture_timestamp_ns < 0:
            raise ValueError('Acquisition timestamp must be nonnegative')
        # Subtract integers before the only ns -> seconds conversion. Never read
        # either current clock here: delivery time is not measurement time.
        elapsed_ns = capture_timestamp_ns - self.perf_counter_anchor_ns
        mapped = self.lsl_anchor_s + elapsed_ns / 1_000_000_000
        if not math.isfinite(mapped):
            raise ValueError('Acquisition timestamp cannot be represented on the LSL clock')
        return mapped

    @classmethod
    def calibrate(
        cls,
        local_clock: Callable[[], float],
        *,
        perf_counter_ns: Callable[[], int] = time.perf_counter_ns,
        observations: int = 8,
    ) -> LslClockMapping:
        """Choose the least delayed bracket around an LSL local-clock reading.

        This records local clock correspondence at setup, not per-sample arrival
        or emission times. Its interval remains available for uncertainty reports.
        """
        if observations < 1:
            raise ValueError('At least one clock observation is required')
        best: LslClockMapping | None = None
        for _ in range(observations):
            before = perf_counter_ns()
            lsl_s = local_clock()
            after = perf_counter_ns()
            if before < 0 or after < before:
                raise ValueError('Monotonic clock calibration bracket is invalid')
            candidate = cls(
                perf_counter_anchor_ns=before + (after - before) // 2,
                lsl_anchor_s=lsl_s,
                calibration_span_ns=after - before,
            )
            if best is None or candidate.calibration_span_ns < best.calibration_span_ns:
                best = candidate
        assert best is not None
        return best
