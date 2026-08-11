"""CSV loading, CLI, and formatting for segment-length diagnostics.

The measurement, statistics, and human-shape assessment logic lives in
``skellyforge.kinematics.segment_lengths`` (single source of truth).
This module provides the freemocap-specific I/O: loading body-3D CSVs,
formatting reports for the terminal, and the ``python -m`` CLI entry point.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from skellyforge.kinematics.segment_lengths import (
    build_segment_length_report,
    SegmentLengthReport,
)


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------


def find_body_csv(path) -> Path:
    """Resolve a body-3D CSV from a recording folder, output_data folder,
    or CSV path.

    Prefers ``mediapipe_body_3d_xyz.csv``; falls back to any
    ``*body_3d_xyz.csv``.
    """
    path = Path(path).expanduser()
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
    """Load a body 3D CSV -> ``{landmark_name: (n_frames, 3)}``.

    Handles two formats:
    - Wide: one row per frame, columns ``{name}_x``, ``{name}_y``, ``{name}_z``
      (legacy freemocap output).
    - Long: columns ``frame, keypoint, x, y, z`` (new pipeline output).
    """
    import pandas as pd

    df = pd.read_csv(csv_path)
    cols = set(df.columns)

    if {"frame", "keypoint", "x", "y", "z"}.issubset(cols):
        # Long format
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

    # Wide format: columns like ``left_shoulder_x``, ``left_shoulder_y``, ...
    x_cols = [c for c in df.columns if c.endswith("_x")]
    if not x_cols:
        raise ValueError(
            f"{csv_path} is neither long-format (frame/keypoint/x/y/z) "
            f"nor wide-format (*_x/*_y/*_z). "
            f"Columns: {list(df.columns)[:10]}..."
        )
    positions = {}
    for x_col in x_cols:
        name = x_col[:-2]  # strip "_x"
        y_col = f"{name}_y"
        z_col = f"{name}_z"
        if y_col not in cols or z_col not in cols:
            continue
        arr = np.column_stack([
            df[x_col].to_numpy(dtype=float),
            df[y_col].to_numpy(dtype=float),
            df[z_col].to_numpy(dtype=float),
        ])
        positions[name] = arr
    return positions


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_report_block(
    report: SegmentLengthReport, *, source: str | None = None
) -> str:
    """Render a formatted ASCII statistics block for the CLI."""
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
            f"  {name:<15}{s.n_valid:>5}{s.mean_mm:>8.1f}"
            f"{s.median_mm:>8.1f}{s.std_mm:>7.1f}"
            f"{s.temporal_cv * 100:>6.1f}{s.min_mm:>8.1f}"
            f"{s.max_mm:>8.1f}{s.implied_height_mm:>10.0f}"
        )
    lines.append("  " + "-" * (width - 2))

    assessable = report.assessable()
    n_frames = max(
        (s.n_frames for s in report.stats.values()), default=0
    )
    coverage = (
        float(
            np.mean(
                [s.valid_fraction for s in report.stats.values()]
            )
        )
        * 100.0
        if report.stats
        else 0.0
    )
    lines.append("  GENERAL STATISTICS")
    lines.append(f"    frames analyzed        : {n_frames}")
    lines.append(
        f"    segments measured      : "
        f"{len(assessable)} / {len(report.stats)}"
    )
    lines.append(f"    mean valid coverage    : {coverage:.1f}%")
    implied = [
        s.implied_height_mm
        for s in assessable.values()
        if np.isfinite(s.implied_height_mm)
    ]
    if implied:
        lines.append(
            f"    implied height (mm)    : mean {np.mean(implied):.0f}  "
            f"median {np.median(implied):.0f}  std {np.std(implied):.0f}  "
            f"cv {report.implied_height_cv * 100:.1f}%"
        )
    if assessable:
        mean_within = (
            float(np.mean([s.temporal_cv for s in assessable.values()]))
            * 100.0
        )
        lines.append(f"    mean within-segment cv : {mean_within:.1f}%")
    symmetry = report.symmetry_diffs()
    if symmetry:
        lines.append(
            "    left/right symmetry    : "
            + "  ".join(
                f"{p} {d * 100:.1f}%"
                for p, d in sorted(symmetry.items())
            )
        )
    lines.append("=" * width)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv=None) -> int:
    """CLI: report body-segment proportions / human-shape.

    Usage:  python -m freemocap.core.kinematics.segment_lengths [path]
    Defaults to FREEMOCAP_TEST_DATA_PATH.
    Exit code 0 = human-shaped, 1 = not, 2 = no data found.
    """
    import argparse
    from freemocap.system.default_paths import FREEMOCAP_TEST_DATA_PATH

    parser = argparse.ArgumentParser(
        description="Body-proportion / 'human-shaped' diagnostic."
    )
    parser.add_argument(
        "recording",
        nargs="?",
        default=FREEMOCAP_TEST_DATA_PATH,
        help="Recording folder, output_data folder, or *_body_3d_xyz.csv",
    )
    args = parser.parse_args(argv)

    try:
        csv_path = find_body_csv(args.recording)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    report = build_segment_length_report(
        load_body_positions_from_csv(csv_path)
    )
    print(format_report_block(report, source=str(csv_path)))

    violations = report.human_shape_violations(check_rigidity=True)
    if violations:
        print("\nVERDICT: NOT human-shaped (FAIL):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(
        f"\nVERDICT: human-shaped (PASS) -- "
        f"implied standing height {report.implied_height_median_mm:.0f}mm"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
