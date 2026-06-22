"""Anatomical segment-length diagnostics.

Measure body-segment lengths from a canonical-named 3D keypoint time series and
assess whether the data is *human-shaped*: segments in anthropometric
proportion, rigid over time, and left/right symmetric.

The reference is the canonical body model's ``bone_length_ratios`` (each bone's
length as a fraction of standing height — Winter 2009 / Drillis & Contini 1966).
Because the checks divide measured length by the canonical ratio, they are
**height-independent**: a genuinely human skeleton implies one consistent
standing height across every segment, so the spread of per-segment implied
heights is the core "is this human-shaped?" signal.

This module is pure measurement + assessment over a ``{landmark_name: (frames, 3)}``
array dict. It is reusable both as a runtime realtime-pipeline diagnostic and in
tests that validate posthoc / realtime mocap output. It does not depend on pytest
or on any particular tracker — callers pass canonical-named positions.

Only the rigorous limb segments (upper arm, forearm, thigh, shank) are assessed:
the canonical model flags its torso/head ratios as rough seeds, so they are
unsuitable for a strict proportionality check.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Segment definitions (canonical COCO landmark names — shared by mediapipe and
# RTMPose for these joints, so both pipelines measure the same segments).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SegmentDef:
    name: str
    proximal: str
    distal: str
    pair: str  # base name shared by the left/right pair, e.g. "upper_arm"

    @property
    def bone_key(self) -> str:
        """Key into the canonical model's bone_length_ratios ("parent->child")."""
        return f"{self.proximal}->{self.distal}"


LIMB_SEGMENTS: tuple[SegmentDef, ...] = (
    SegmentDef("left_upper_arm", "left_shoulder", "left_elbow", "upper_arm"),
    SegmentDef("right_upper_arm", "right_shoulder", "right_elbow", "upper_arm"),
    SegmentDef("left_forearm", "left_elbow", "left_wrist", "forearm"),
    SegmentDef("right_forearm", "right_elbow", "right_wrist", "forearm"),
    SegmentDef("left_thigh", "left_hip", "left_knee", "thigh"),
    SegmentDef("right_thigh", "right_hip", "right_knee", "thigh"),
    SegmentDef("left_shank", "left_knee", "left_ankle", "shank"),
    SegmentDef("right_shank", "right_knee", "right_ankle", "shank"),
)


@lru_cache(maxsize=1)
def canonical_bone_length_ratios() -> dict[str, float]:
    """Bone-length ratios (length / standing height) from the canonical body model.

    Single source of truth: skellyforge's ``canonical_body.yaml`` via
    ``AnatomicalStructure``. Cached — loaded once per process.
    """
    from skellyforge.skellymodels.models.anatomical_structure import AnatomicalStructure
    from skellyforge.skellymodels.models.tracking_model_info import CanonicalBodyModelInfo

    anatomy = AnatomicalStructure.from_model_info(CanonicalBodyModelInfo(), "body")
    ratios = anatomy.bone_length_ratios
    if not ratios:
        raise ValueError("Canonical body model exposes no bone_length_ratios")
    return dict(ratios)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanShapeThresholds:
    """Pass/fail bars for the human-shape and equivalence checks (balanced)."""
    max_temporal_cv: float = 0.15        # per-segment length stability over time
    max_proportion_cv: float = 0.15      # spread of implied heights across segments
    max_symmetry_diff: float = 0.15      # |L-R| / mean for each paired segment
    min_height_mm: float = 1000.0        # plausible standing-height range (mm)
    max_height_mm: float = 2200.0
    max_equivalence_diff: float = 0.25   # |a-b| / b for realtime-vs-posthoc medians
    min_valid_fraction: float = 0.25     # a segment needs ≥ this fraction of valid frames
    min_assessable_segments: int = 4     # need at least this many usable segments


DEFAULT_THRESHOLDS = HumanShapeThresholds()


# ---------------------------------------------------------------------------
# Per-segment stats
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SegmentStats:
    name: str
    pair: str
    ratio: float
    mean_mm: float
    median_mm: float
    std_mm: float
    mad_mm: float  # median absolute deviation (robust spread)
    min_mm: float
    max_mm: float
    n_valid: int
    n_frames: int

    @property
    def temporal_cv(self) -> float:
        # Robust CV: MAD scaled to a std-equivalent (×1.4826), over the median.
        # Robust to transient bad frames (occlusion / foreshortening, e.g. during
        # the calibration portion of the clip) that would inflate a plain std.
        # This is the spread used by the human-shape rigidity check.
        robust_std = 1.4826 * self.mad_mm
        return robust_std / self.median_mm if self.median_mm > 0 else float("inf")

    @property
    def cv(self) -> float:
        """Classic coefficient of variation (std / mean)."""
        return self.std_mm / self.mean_mm if self.mean_mm > 0 else float("inf")

    @property
    def range_mm(self) -> float:
        return self.max_mm - self.min_mm

    @property
    def implied_height_mm(self) -> float:
        return self.median_mm / self.ratio if self.ratio > 0 else float("nan")

    @property
    def valid_fraction(self) -> float:
        return self.n_valid / self.n_frames if self.n_frames else 0.0


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def measure_segment_lengths(
    canonical_positions: dict[str, np.ndarray],
    segments: tuple[SegmentDef, ...] = LIMB_SEGMENTS,
) -> dict[str, np.ndarray]:
    """Per-frame Euclidean length of each segment.

    Parameters
    ----------
    canonical_positions
        ``{canonical_landmark_name: (n_frames, 3) array}``. Missing landmarks or
        NaN coordinates yield NaN lengths for the affected frames.

    Returns ``{segment_name: (n_frames,) array}`` for segments whose endpoints
    are both present in the dict.
    """
    lengths: dict[str, np.ndarray] = {}
    for seg in segments:
        proximal = canonical_positions.get(seg.proximal)
        distal = canonical_positions.get(seg.distal)
        if proximal is None or distal is None:
            continue
        proximal = np.asarray(proximal, dtype=float)
        distal = np.asarray(distal, dtype=float)
        lengths[seg.name] = np.linalg.norm(distal - proximal, axis=-1)
    return lengths


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class SegmentLengthReport:
    """Per-segment stats + aggregate human-shape metrics."""

    stats: dict[str, SegmentStats]
    thresholds: HumanShapeThresholds = DEFAULT_THRESHOLDS

    def assessable(self) -> dict[str, SegmentStats]:
        """Segments with enough valid frames to trust."""
        return {
            name: s
            for name, s in self.stats.items()
            if s.valid_fraction >= self.thresholds.min_valid_fraction and s.median_mm > 0
        }

    @property
    def implied_heights(self) -> dict[str, float]:
        return {n: s.implied_height_mm for n, s in self.assessable().items()}

    @property
    def implied_height_median_mm(self) -> float:
        vals = [h for h in self.implied_heights.values() if np.isfinite(h)]
        return float(np.median(vals)) if vals else float("nan")

    @property
    def implied_height_cv(self) -> float:
        vals = [h for h in self.implied_heights.values() if np.isfinite(h)]
        if len(vals) < 2:
            return float("inf")
        med = float(np.median(vals))
        return float(np.std(vals)) / med if med > 0 else float("inf")

    def symmetry_diffs(self) -> dict[str, float]:
        """Relative left/right length difference per pair (e.g. 'upper_arm')."""
        assessable = self.assessable()
        by_pair: dict[str, dict[str, float]] = {}
        for name, s in assessable.items():
            side = "left" if name.startswith("left_") else "right"
            by_pair.setdefault(s.pair, {})[side] = s.median_mm
        diffs: dict[str, float] = {}
        for pair, sides in by_pair.items():
            if "left" in sides and "right" in sides:
                lo, hi = sides["left"], sides["right"]
                mean = (lo + hi) / 2.0
                diffs[pair] = abs(lo - hi) / mean if mean > 0 else float("inf")
        return diffs

    def human_shape_violations(self, *, check_rigidity: bool = True) -> list[str]:
        """Return human-readable violation strings; empty list means it passes."""
        t = self.thresholds
        violations: list[str] = []

        assessable = self.assessable()
        if len(assessable) < t.min_assessable_segments:
            violations.append(
                f"only {len(assessable)} segment(s) have ≥{t.min_valid_fraction:.0%} "
                f"valid frames (need {t.min_assessable_segments})"
            )
            return violations  # nothing else is meaningful

        cv = self.implied_height_cv
        if cv > t.max_proportion_cv:
            violations.append(
                f"implied-height CV {cv:.3f} > {t.max_proportion_cv} "
                f"(segments disagree on body scale → not human-proportioned)"
            )

        median_h = self.implied_height_median_mm
        if not (t.min_height_mm <= median_h <= t.max_height_mm):
            violations.append(
                f"implied standing height {median_h:.0f}mm outside plausible "
                f"[{t.min_height_mm:.0f}, {t.max_height_mm:.0f}]mm"
            )

        if check_rigidity:
            for name, s in assessable.items():
                if s.temporal_cv > t.max_temporal_cv:
                    violations.append(
                        f"{name} temporal CV {s.temporal_cv:.3f} > {t.max_temporal_cv} "
                        f"(length not stable over time)"
                    )

        for pair, diff in self.symmetry_diffs().items():
            if diff > t.max_symmetry_diff:
                violations.append(
                    f"{pair} left/right differ by {diff:.1%} > {t.max_symmetry_diff:.0%}"
                )

        return violations

    def summary(self) -> str:
        lines = ["Segment-length report (median mm | temporal CV | implied height mm):"]
        for name in sorted(self.stats):
            s = self.stats[name]
            lines.append(
                f"  {name:18s} {s.median_mm:7.1f} | cv={s.temporal_cv:5.3f} | "
                f"H={s.implied_height_mm:7.1f} | valid={s.valid_fraction:.0%}"
            )
        lines.append(
            f"  -> implied height: median={self.implied_height_median_mm:.0f}mm "
            f"cv={self.implied_height_cv:.3f}"
        )
        sym = self.symmetry_diffs()
        if sym:
            lines.append(
                "  -> symmetry: " + ", ".join(f"{p}={d:.1%}" for p, d in sorted(sym.items()))
            )
        return "\n".join(lines)


def report_from_segment_lengths(
    lengths_by_segment: dict[str, np.ndarray],
    *,
    ratios: dict[str, float] | None = None,
    segments: tuple[SegmentDef, ...] = LIMB_SEGMENTS,
    thresholds: HumanShapeThresholds = DEFAULT_THRESHOLDS,
) -> SegmentLengthReport:
    """Build a stats report from already-measured per-segment length series."""
    if ratios is None:
        ratios = canonical_bone_length_ratios()
    by_name = {seg.name: seg for seg in segments}

    stats: dict[str, SegmentStats] = {}
    for name, length_series in lengths_by_segment.items():
        seg = by_name.get(name)
        if seg is None:
            continue
        ratio = ratios.get(seg.bone_key)
        if ratio is None or ratio <= 0.0:
            raise ValueError(
                f"No positive canonical bone-length ratio for '{seg.bone_key}'"
            )
        series = np.asarray(length_series, dtype=float)
        finite = series[np.isfinite(series) & (series > 0.0)]
        n_frames = int(series.shape[0])
        if finite.size == 0:
            stats[name] = SegmentStats(
                name, seg.pair, ratio, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, n_frames
            )
            continue
        median = float(np.median(finite))
        stats[name] = SegmentStats(
            name=name,
            pair=seg.pair,
            ratio=ratio,
            mean_mm=float(np.mean(finite)),
            median_mm=median,
            std_mm=float(np.std(finite)),
            mad_mm=float(np.median(np.abs(finite - median))),
            min_mm=float(np.min(finite)),
            max_mm=float(np.max(finite)),
            n_valid=int(finite.size),
            n_frames=n_frames,
        )
    return SegmentLengthReport(stats=stats, thresholds=thresholds)


def build_segment_length_report(
    canonical_positions: dict[str, np.ndarray],
    *,
    ratios: dict[str, float] | None = None,
    segments: tuple[SegmentDef, ...] = LIMB_SEGMENTS,
    thresholds: HumanShapeThresholds = DEFAULT_THRESHOLDS,
) -> SegmentLengthReport:
    """Measure segment lengths and build a stats report over a position time series."""
    return report_from_segment_lengths(
        measure_segment_lengths(canonical_positions, segments),
        ratios=ratios,
        segments=segments,
        thresholds=thresholds,
    )


# ---------------------------------------------------------------------------
# Streaming monitor (live realtime diagnostic)
# ---------------------------------------------------------------------------

# Defaults tuned for ~30 fps: keep ~4 s of history, re-assess ~ every 2 s.
DEFAULT_DIAGNOSTIC_WINDOW: int = 120
DEFAULT_DIAGNOSTIC_INTERVAL: int = 60


class StreamingSegmentLengthMonitor:
    """Rolling-window segment-length monitor for live use in a realtime pipeline.

    ``update`` is called once per frame with the current canonical-named 3D points
    (cheap: one distance per limb segment). ``report`` summarizes the rolling
    window into a ``SegmentLengthReport`` for periodic human-shape assessment.

    Designed to run in the realtime aggregator's hot loop, so per-frame work is
    minimal and report-building is left to the caller's chosen cadence.
    """

    def __init__(
        self,
        *,
        window: int = DEFAULT_DIAGNOSTIC_WINDOW,
        segments: tuple[SegmentDef, ...] = LIMB_SEGMENTS,
        thresholds: HumanShapeThresholds = DEFAULT_THRESHOLDS,
        ratios: dict[str, float] | None = None,
    ) -> None:
        self.window = window
        self.segments = segments
        self.thresholds = thresholds
        self._ratios = ratios if ratios is not None else canonical_bone_length_ratios()
        self._buffers = {seg.name: deque(maxlen=window) for seg in segments}
        self._n_seen = 0

    @property
    def n_seen(self) -> int:
        return self._n_seen

    def update(self, canonical_positions: dict[str, np.ndarray]) -> None:
        """Append this frame's per-segment lengths to the rolling buffers.

        Missing endpoints append NaN (keeps the window time-consistent); an empty
        dict (no triangulation this frame) is fine.
        """
        for seg in self.segments:
            proximal = canonical_positions.get(seg.proximal)
            distal = canonical_positions.get(seg.distal)
            if proximal is None or distal is None:
                self._buffers[seg.name].append(float("nan"))
                continue
            length = float(
                np.linalg.norm(
                    np.asarray(distal, dtype=float).reshape(3)
                    - np.asarray(proximal, dtype=float).reshape(3)
                )
            )
            self._buffers[seg.name].append(length if np.isfinite(length) and length > 0 else float("nan"))
        self._n_seen += 1

    def report(self) -> SegmentLengthReport:
        lengths = {name: np.asarray(buf, dtype=float) for name, buf in self._buffers.items()}
        return report_from_segment_lengths(
            lengths, ratios=self._ratios, segments=self.segments, thresholds=self.thresholds
        )


def equivalence_violations(
    report_a: SegmentLengthReport,
    report_b: SegmentLengthReport,
    *,
    thresholds: HumanShapeThresholds = DEFAULT_THRESHOLDS,
    label_a: str = "A",
    label_b: str = "B",
) -> list[str]:
    """Compare per-segment median lengths between two reports (e.g. realtime vs posthoc).

    ``report_b`` is the reference (denominator). Returns human-readable violations;
    empty list means the two are equivalent within ``max_equivalence_diff``.
    """
    a_ok = report_a.assessable()
    b_ok = report_b.assessable()
    common = sorted(set(a_ok) & set(b_ok))
    violations: list[str] = []
    if len(common) < thresholds.min_assessable_segments:
        violations.append(
            f"only {len(common)} comparable segment(s) (need "
            f"{thresholds.min_assessable_segments})"
        )
        return violations
    for name in common:
        a = a_ok[name].median_mm
        b = b_ok[name].median_mm
        diff = abs(a - b) / b if b > 0 else float("inf")
        if diff > thresholds.max_equivalence_diff:
            violations.append(
                f"{name}: {label_a}={a:.0f}mm vs {label_b}={b:.0f}mm "
                f"({diff:.1%} > {thresholds.max_equivalence_diff:.0%})"
            )
    return violations


# ---------------------------------------------------------------------------
# Loading saved recordings + CLI
# ---------------------------------------------------------------------------


def find_body_csv(path) -> Path:
    """Resolve a body-3D CSV from a recording folder, output_data folder, or CSV path.

    Prefers ``mediapipe_body_3d_xyz.csv``; falls back to any ``*body_3d_xyz.csv``.
    """
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".csv":
        return path
    for directory in (path, path / "output_data"):
        if not directory.is_dir():
            continue
        preferred = directory / "mediapipe_body_3d_xyz.csv"
        if preferred.exists():
            return preferred
        matches = sorted(directory.glob("*body_3d_xyz.csv"))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No *body_3d_xyz.csv found under {path}")


def load_body_positions_from_csv(csv_path) -> dict[str, np.ndarray]:
    """Load a long-format ``frame,keypoint,x,y,z`` body CSV → ``{name: (frames, 3)}``."""
    import pandas as pd  # local import: keep pandas out of the realtime hot-loop import path

    df = pd.read_csv(csv_path)
    expected = {"frame", "keypoint", "x", "y", "z"}
    if not expected.issubset(df.columns):
        raise ValueError(
            f"{csv_path} missing columns {expected - set(df.columns)} (has {list(df.columns)})"
        )
    frames = np.sort(df["frame"].unique())
    n_frames = len(frames)
    frame_to_idx = {int(f): i for i, f in enumerate(frames)}
    positions: dict[str, np.ndarray] = {}
    for keypoint, group in df.groupby("keypoint"):
        arr = np.full((n_frames, 3), np.nan)
        idx = group["frame"].map(frame_to_idx).to_numpy()
        arr[idx, 0] = group["x"].to_numpy()
        arr[idx, 1] = group["y"].to_numpy()
        arr[idx, 2] = group["z"].to_numpy()
        positions[str(keypoint)] = arr
    return positions


def format_report_block(report: SegmentLengthReport, *, source: str | None = None) -> str:
    """Render a nicely formatted, ASCII-only statistics block for the CLI.

    A per-segment table (mean / median / std / CV / min / max / implied height)
    followed by a general-statistics section.
    """
    width = 77
    lines: list[str] = []
    lines.append("=" * width)
    lines.append("  BODY SEGMENT-LENGTH REPORT  (lengths in mm)")
    if source:
        lines.append(f"  source: {source}")
    lines.append("=" * width)
    lines.append(
        f"  {'segment':<15}{'n':>5}{'mean':>8}{'median':>8}{'std':>7}"
        f"{'cv%':>6}{'min':>8}{'max':>8}{'impl_H':>10}"
    )
    lines.append("  " + "-" * (width - 2))
    for name in sorted(report.stats):
        s = report.stats[name]
        if s.n_valid == 0:
            lines.append(f"  {name:<15}{0:>5}      (no valid frames)")
            continue
        lines.append(
            f"  {name:<15}{s.n_valid:>5}{s.mean_mm:>8.1f}{s.median_mm:>8.1f}"
            f"{s.std_mm:>7.1f}{s.cv * 100:>6.1f}{s.min_mm:>8.1f}{s.max_mm:>8.1f}"
            f"{s.implied_height_mm:>10.0f}"
        )
    lines.append("  " + "-" * (width - 2))

    assessable = report.assessable()
    n_frames = max((s.n_frames for s in report.stats.values()), default=0)
    coverage = (
        float(np.mean([s.valid_fraction for s in report.stats.values()])) * 100.0
        if report.stats else 0.0
    )
    lines.append("  GENERAL STATISTICS")
    lines.append(f"    frames analyzed        : {n_frames}")
    lines.append(f"    segments measured      : {len(assessable)} / {len(report.stats)}")
    lines.append(f"    mean valid coverage    : {coverage:.1f}%")
    implied = [s.implied_height_mm for s in assessable.values() if np.isfinite(s.implied_height_mm)]
    if implied:
        lines.append(
            f"    implied height (mm)    : mean {np.mean(implied):.0f}  "
            f"median {np.median(implied):.0f}  std {np.std(implied):.0f}  "
            f"cv {report.implied_height_cv * 100:.1f}%"
        )
    if assessable:
        mean_within = float(np.mean([s.cv for s in assessable.values()])) * 100.0
        lines.append(f"    mean within-segment cv : {mean_within:.1f}%")
    symmetry = report.symmetry_diffs()
    if symmetry:
        lines.append(
            "    left/right symmetry    : "
            + "  ".join(f"{p} {d * 100:.1f}%" for p, d in sorted(symmetry.items()))
        )
    lines.append("=" * width)
    return "\n".join(lines)


def _main(argv=None) -> int:
    """CLI: report body-segment proportions / human-shape for a processed recording.

    Usage:  python -m freemocap.core.kinematics.segment_lengths <recording_or_output_dir_or_csv>
    Exit code 0 = human-shaped, 1 = not, 2 = no data found.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Body-proportion / 'human-shaped' diagnostic for a processed recording."
    )
    parser.add_argument(
        "recording",
        help="A recording folder, an output_data folder, or a *_body_3d_xyz.csv file.",
    )
    args = parser.parse_args(argv)

    try:
        csv_path = find_body_csv(args.recording)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    report = build_segment_length_report(load_body_positions_from_csv(csv_path))
    print(format_report_block(report, source=str(csv_path)))

    violations = report.human_shape_violations(check_rigidity=True)
    if violations:
        print("\nVERDICT: NOT human-shaped (FAIL):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(
        f"\nVERDICT: human-shaped (PASS) -- implied standing height "
        f"{report.implied_height_median_mm:.0f}mm"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
