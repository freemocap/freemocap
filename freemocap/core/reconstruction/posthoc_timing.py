"""A flat, per-stage timing accumulator for batch (posthoc) pipeline runs.

The streaming pipeline publishes rolling timing samples over pubsub; a posthoc run is a
single batch, so it wants the opposite: accumulate each stage's elapsed time once and
print one human-readable table at the end. This is the reporting half of that contract —
the driver records, this formats.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StageTiming:
    """One named stage's accumulated wall-clock time."""

    name: str
    elapsed_seconds: float
    call_count: int = 1
    note: str = ""


@dataclass
class PosthocTimingReport:
    """Accumulates per-stage wall-clock times for one batch run and formats a table."""

    stages: list[StageTiming] = field(default_factory=list)

    def record(
        self,
        name: str,
        elapsed_seconds: float,
        *,
        call_count: int = 1,
        note: str = "",
    ) -> None:
        self.stages.append(
            StageTiming(
                name=name,
                elapsed_seconds=elapsed_seconds,
                call_count=call_count,
                note=note,
            )
        )

    @property
    def total_seconds(self) -> float:
        return sum(stage.elapsed_seconds for stage in self.stages)

    def summary_table(self) -> str:
        """One aligned table: stage, seconds, share, ms/call, calls, note."""
        total = self.total_seconds or 1e-12
        rows = [
            (
                stage.name,
                stage.elapsed_seconds,
                stage.elapsed_seconds / total * 100.0,
                stage.elapsed_seconds * 1000.0 / stage.call_count,
                stage.call_count,
                stage.note,
            )
            for stage in self.stages
        ]
        header = (
            f"{'stage':<30} {'seconds':>9} {'%':>7} {'ms/call':>10} {'calls':>7}  note"
        )
        bar = "-" * len(header)
        body = [
            f"{name:<30} {seconds:>9.3f} {pct:>6.1f}% {ms_per_call:>10.3f} {calls:>7}  {note}"
            for name, seconds, pct, ms_per_call, calls, note in rows
        ]
        total_row = f"{'TOTAL':<30} {total:>9.3f} {'100.0%':>7}"
        return "\n".join(
            [
                "Posthoc pipeline timing report",
                header,
                bar,
                *body,
                bar,
                total_row,
            ]
        )
