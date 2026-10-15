"""Bounded, thread-safe wall-clock diagnostics; overlapping rows are not additive."""

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from threading import Lock
from time import perf_counter

from tabulate import tabulate

logger = logging.getLogger(__name__)


@dataclass
class TimingSummary:
    count: int = 0
    total: float = 0.0
    maximum: float = 0.0
    first: float = 0.0


class PerformanceReport:
    def __init__(self) -> None:
        self._lock = Lock()
        self._rows: dict[str, TimingSummary] = {}
        self._counts: dict[str, int] = {}
        self._started = perf_counter()
        self.frames = 0
        self.images = 0
        self.details: list[str] = []

    @property
    def elapsed_seconds(self) -> float:
        return perf_counter() - self._started

    def record(self, name: str, seconds: float) -> None:
        with self._lock:
            row = self._rows.setdefault(name, TimingSummary())
            if row.count == 0:
                row.first = seconds
            row.count += 1
            row.total += seconds
            row.maximum = max(row.maximum, seconds)

    def increment_counts(self, counts: dict[str, int]) -> None:
        with self._lock:
            for name, count in counts.items():
                self._counts[name] = self._counts.get(name, 0) + count

    def counts_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    @contextmanager
    def measure(self, name: str):
        started = perf_counter()
        try:
            yield
        finally:
            self.record(name, perf_counter() - started)

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            return {name: dict(count=row.count, total_s=row.total,
                mean_ms=1000 * row.total / row.count, max_ms=1000 * row.maximum,
                first_ms=1000 * row.first,
                mean_after_first_ms=1000 * (row.total - row.first) / (row.count - 1)
                    if row.count > 1 else 0.0)
                for name, row in self._rows.items()}

    def log(self, *, pipeline_id: str, outcome: str) -> None:
        elapsed = self.elapsed_seconds
        rows = self.snapshot()
        lines = [f"Posthoc performance [{pipeline_id}] outcome={outcome}; wall={elapsed:.3f}s",
            f"Completed detection: {self.frames} synchronized frames; {self.images} camera images.",
            "Wall-clock timings, not GPU kernel timings. Worker and coordinator rows overlap; do not sum them.",
            "Coordinator waits measure exposed blocking; worker rows measure work, including work hidden by overlap."]
        lines[1:1] = self.details
        lines.extend(f"count {name}: {count}" for name, count in sorted(self.counts_snapshot().items()))
        if rows:
            lines.extend(["", tabulate(
                [[name, row["count"], f"{row['total_s']:.3f}", f"{row['mean_ms']:.3f}",
                  f"{row['first_ms']:.3f}", f"{row['mean_after_first_ms']:.3f}" if row["count"] > 1 else "-",
                  f"{row['max_ms']:.3f}"]
                 for name, row in sorted(rows.items())],
                headers=["Stage", "Calls", "Total (s)", "Mean (ms)", "First (ms)",
                         "After first (ms)", "Max (ms)"],
                tablefmt="outline", disable_numparse=True,
                colalign=("left", "right", "right", "right", "right", "right", "right"),
            ), "After first: mean excluding the first call; '-' means only one call."])
        else:
            lines.extend(["", "No stage timings recorded."])
        detection = rows.get("detection.total", {}).get("total_s", 0.0)
        if detection:
            lines.insert(2, f"Detection throughput: {self.frames / detection:.2f} synchronized frames/s; "
                         f"{self.images / detection:.2f} camera images/s (includes setup and video finalization).")
        logger.info("\n%s\n", "\n".join(lines))
