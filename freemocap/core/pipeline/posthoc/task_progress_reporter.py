"""
TaskProgressReporter: typed progress-reporting interface for task functions.

Task functions receive a TaskProgressReporter instead of a bare Callable.
Call reporter.report(stage=SomeStage.FOO) at each meaningful step.

Use TaskProgressReporter.noop() when no reporting is needed (e.g. in tests
or when the aggregation node has no WebSocket queue available).
"""
from __future__ import annotations

from collections.abc import Callable


class TaskProgressReporter:
    """
    Wraps the underlying progress callback with a named, keyword-only interface.

    Args:
        callback: receives (stage: str, detail: str, fraction: float).
                  Pass a pipeline_phases enum value for stage; its string
                  representation is forwarded to the callback automatically.
    """

    def __init__(self, callback: Callable[[str, str, float], None]) -> None:
        self._callback = callback

    def report(
        self,
        *,
        stage: str,
        detail: str = "",
        fraction: float = 0.0,
    ) -> None:
        """Emit a progress update.

        Args:
            stage:    A phase/stage enum value (or plain string as fallback).
                      All enums in pipeline_phases stringify to their value.
            detail:   Human-readable description shown in the UI.
            fraction: Completion fraction in [0.0, 1.0].  Most named stages
                      leave this at 0.0 (indeterminate bar); use it only when
                      you have a genuine measured fraction.
        """
        self._callback(str(stage), detail, fraction)

    @classmethod
    def noop(cls) -> TaskProgressReporter:
        """Returns a silent reporter that discards all progress updates."""
        return cls(callback=lambda *_: None)
