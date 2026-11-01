"""
PipelineTimingReporter: a daemon thread (run inside the aggregator subprocess)
that subscribes to PipelineTimingTopic, maintains rolling per-stage buffers,
and periodically prints one consolidated report.

Camera-node samples for the same stage collapse across cameras into ensemble
statistics so adding cameras doesn't multiply log volume. A `cam-spread`
column surfaces straggler cameras (max - min of per-camera means).
"""
import collections
import logging
import threading
import time
from dataclasses import dataclass, field
from queue import Empty

import numpy as np
from skellycam.core.types.type_overloads import TopicSubscriptionQueue
from tabulate import tabulate

from freemocap.core.pipeline.pipeline_stage_timer import ROLLING_WINDOW_FRAMES

logger = logging.getLogger(__name__)

REPORT_INTERVAL_SECONDS: float = 30.0
SEPARATOR_WIDTH: int = 100
PRECISION: int = 2

# Presentation order only. Independently sampled stage windows are not an
# accounting partition: optional stages can cover different frames and workers
# overlap. Neither ratios nor sums of their medians express a share of latency.
@dataclass(frozen=True)
class _SectionLayout:
    substages: tuple[str, ...]
    wrapper: str | None
    framing: tuple[str, ...] = ()


SECTION_LAYOUTS: dict[str, _SectionLayout] = {
    "aggregator": _SectionLayout(
        substages=(
            "skeleton_triangulation",
            "charuco_triangulation",
            "keypoint_filter",
            "velocity_gate",
            "skeleton_filter",
            "skeleton_fitting",
        ),
        wrapper="full_frame_processing",
        framing=("frame_collection_wait", "loop_time"),
    ),
    "skeleton_inference": _SectionLayout(
        substages=("frame_read", "predict_batch"),
        wrapper=None,
        framing=("predict_per_camera", "dropped_frames"),
    ),
    "camera": _SectionLayout(
        substages=("skeleton_detection", "charuco_detection"),
        wrapper="total_camera_node",
    ),
}


# Describe the actual timer boundaries, not an inferred execution graph.
STAGE_SCOPES: dict[str, str] = {
    "total_camera_node": "detection section / frame, including skips; excludes read/publish",
    "skeleton_detection": "detector call / camera image",
    "charuco_detection": "detector call / camera image; skipped attempts absent",
    "full_frame_processing": "aggregation / group frame; excludes collection and output publish",
    "frame_collection_wait": "request to collected results; overlaps previous aggregation",
    "loop_time": "interval between completed aggregation timings",
    "frame_read": "read camera images / group request",
    "predict_batch": "submit to result / batch; includes inference service wait",
    "predict_per_camera": "amortized batch duration / image; not image latency",
    "dropped_frames": "discarded requests / drain with drops; zero-drop drains absent",
}


@dataclass
class PipelineTimingReporter:
    """Subscribes to PipelineTimingTopic and emits a consolidated report periodically."""

    name: str
    timing_sub: TopicSubscriptionQueue
    stop_event: threading.Event
    expected_camera_count: int = 0
    report_interval: float = REPORT_INTERVAL_SECONDS

    # Per-camera buffers: (camera_id, stage) -> deque
    _camera_samples: dict[tuple[str, str], collections.deque] = field(default_factory=dict)
    # Non-camera node buffers: (node_kind, stage) -> deque
    _node_samples: dict[tuple[str, str], collections.deque] = field(default_factory=dict)
    # Track the most recent label seen per node_kind for nicer section headers
    _node_labels: dict[str, str] = field(default_factory=dict)

    _thread: threading.Thread | None = None
    _new_data_since_last_report: bool = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name=f"PipelineTimingReporter-{self.name}",
            daemon=True,
        )
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        from freemocap.pubsub.pubsub_topics import PipelineTimingMessage  # noqa: TC001

        last_report = time.perf_counter()
        try:
            while not self.stop_event.is_set():
                try:
                    msg: PipelineTimingMessage = self.timing_sub.get(timeout=0.5)
                except Empty:
                    msg = None
                except InterruptedError:
                    # Windows Ctrl+C interrupts the wait syscall during
                    # shutdown; treat as an empty tick and re-check stop_event.
                    msg = None
                if msg is not None:
                    self._ingest(msg)

                now = time.perf_counter()
                if now - last_report >= self.report_interval:
                    last_report = now
                    if self._new_data_since_last_report:
                        self._new_data_since_last_report = False
                        self._print_report()
        except Exception as e:
            logger.error(f"PipelineTimingReporter [{self.name}] crashed: {e}", exc_info=True)

    def _ingest(self, msg) -> None:
        self._new_data_since_last_report = True
        if msg.node_label:
            self._node_labels[msg.node_kind] = msg.node_label
        if msg.node_kind == "camera" and msg.camera_id is not None:
            for stage, values in msg.samples.items():
                key = (msg.camera_id, stage)
                if key not in self._camera_samples:
                    self._camera_samples[key] = collections.deque(maxlen=ROLLING_WINDOW_FRAMES)
                self._camera_samples[key].extend(values)
        else:
            for stage, values in msg.samples.items():
                key = (msg.node_kind, stage)
                if key not in self._node_samples:
                    self._node_samples[key] = collections.deque(maxlen=ROLLING_WINDOW_FRAMES)
                self._node_samples[key].extend(values)

    def _print_report(self) -> None:
        if not self._camera_samples and not self._node_samples:
            return

        sep = "─" * SEPARATOR_WIDTH
        sections: list[str] = [
            sep, f"Pipeline Timing Report — {self.name}",
            f"Latest {ROLLING_WINDOW_FRAMES} samples per stage per node; windows are unpaired, not a shared time interval.",
            "Wall-clock durations: workers and nested rows overlap; do not sum rows or infer end-to-end latency.",
            "Samples count recorded calls/events, not necessarily processed frames. Camera rows pool images across cameras.",
            "Cam-spread is max minus min of per-camera means in the row's unit.",
            "",
        ]

        for kind in ("aggregator", "skeleton_inference"):
            stage_to_arr = {
                stage: np.array(self._node_samples[(k, stage)])
                for (k, stage) in self._node_samples.keys()
                if k == kind
            }
            if not stage_to_arr:
                continue
            label = self._node_labels.get(kind, kind)
            table = _build_table(
                stage_to_samples=stage_to_arr,
                layout=SECTION_LAYOUTS.get(kind),
            )
            sections.append("")
            sections.append(f"[ {label} ]")
            sections.append(table)

        # Camera ensemble: collapse across camera_id for each stage
        if self._camera_samples:
            cam_ids = sorted({cam for (cam, _) in self._camera_samples.keys()})
            stages = sorted({stage for (_, stage) in self._camera_samples.keys()})
            stage_to_pooled: dict[str, np.ndarray] = {}
            stage_to_cam_spread: dict[str, float] = {}
            for stage in stages:
                samples_per_cam = [
                    np.array(self._camera_samples[(cam, stage)])
                    for cam in cam_ids
                    if (cam, stage) in self._camera_samples
                       and len(self._camera_samples[(cam, stage)]) > 0
                ]
                if not samples_per_cam:
                    continue
                stage_to_pooled[stage] = np.concatenate(samples_per_cam)
                per_cam_means = [float(np.mean(s)) for s in samples_per_cam]
                stage_to_cam_spread[stage] = (
                    max(per_cam_means) - min(per_cam_means) if len(per_cam_means) > 1 else 0.0
                )

            if stage_to_pooled:
                table = _build_table(
                    stage_to_samples=stage_to_pooled,
                    layout=SECTION_LAYOUTS.get("camera"),
                    cam_spread_by_stage=stage_to_cam_spread,
                )
                seen = len(cam_ids)
                if self.expected_camera_count and self.expected_camera_count != seen:
                    cam_header = (
                        f"[ Camera ensemble — {seen}/{self.expected_camera_count} "
                        f"cameras reporting (pooled samples) ]"
                    )
                else:
                    total = self.expected_camera_count or seen
                    cam_header = f"[ Camera ensemble — {total} cameras (pooled samples) ]"
                sections.append("")
                sections.append(cam_header)
                sections.append(table)

        sections.append(sep)
        logger.info("\n" + "\n".join(sections))


def _build_table(
        *,
        stage_to_samples: dict[str, np.ndarray],
        layout: _SectionLayout | None,
        cam_spread_by_stage: dict[str, float] | None = None,
) -> str:
    """Build a tabulated stage-statistics table for one section.

    Layout controls ordering only. Samples have no frame identities, so even
    equal-length stage and wrapper windows cannot establish paired accounting.
    Report the observed distributions without inventing percentages.
    """
    p = PRECISION
    headers = ["Stage", "Samples", "Unit", "Median", "Mean", "Std", "Q1", "Q3"]
    if cam_spread_by_stage is not None:
        headers.append("Cam-spread")
    headers.append("Scope")

    if layout is None:
        layout = _SectionLayout(
            substages=tuple(sorted(stage_to_samples.keys())),
            wrapper=None,
            framing=(),
        )

    present_substages = [s for s in layout.substages if s in stage_to_samples]
    present_framing = [s for s in layout.framing if s in stage_to_samples]
    wrapper = layout.wrapper if layout.wrapper in stage_to_samples else None
    # Surface anything we didn't classify so a new stage doesn't silently vanish.
    classified = set(present_substages) | set(present_framing) | ({wrapper} if wrapper else set())
    extras = sorted(s for s in stage_to_samples.keys() if s not in classified)

    def _row(stage: str, samples: np.ndarray) -> list[str]:
        unit = "count" if stage == "dropped_frames" else "ms"
        scope = STAGE_SCOPES.get(stage, "recorded stage call")
        if len(samples) == 0:
            row = [stage, "0", unit, "-", "-", "-", "-", "-"]
            if cam_spread_by_stage is not None:
                row.append("-")
            row.append(scope)
            return row
        median = float(np.median(samples))
        row = [
            stage,
            str(len(samples)),
            unit,
            f"{median:.{p}f}",
            f"{np.mean(samples):.{p}f}",
            f"{np.std(samples):.{p}f}",
            f"{np.percentile(samples, 25):.{p}f}",
            f"{np.percentile(samples, 75):.{p}f}",
        ]
        if cam_spread_by_stage is not None:
            row.append(f"{cam_spread_by_stage.get(stage, 0.0):.{p}f}")
        row.append(scope)
        return row

    rows: list[list[str]] = []
    blank_row = [""] * len(headers)

    for stage in present_substages:
        rows.append(_row(stage, stage_to_samples[stage]))

    if wrapper is not None:
        wrapper_row = _row(wrapper, stage_to_samples[wrapper])
        wrapper_row[0] = f"WRAPPER: {wrapper}"
        rows.append(wrapper_row)

    if present_framing or extras:
        rows.append(blank_row)
        for stage in present_framing + extras:
            rows.append(_row(stage, stage_to_samples[stage]))

    return tabulate(
        rows,
        headers=headers,
        tablefmt="simple",
        stralign="left",
        numalign="right",
        disable_numparse=True,
    )
