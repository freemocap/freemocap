"""Descriptive statistics for diagnostic output; no acceptance thresholds."""

import numpy as np


DISTRIBUTION_COLUMNS = ['N', 'NaN %', 'Inf %', 'Mean', 'SD', 'Min', 'P05', 'Median', 'P95', 'Max']


def distribution_row(values) -> list:
    """Finite samples, population SD, and empirical percentiles (not confidence intervals)."""
    samples = np.asarray(values, dtype=float).ravel()
    nan_percent = float(np.isnan(samples).mean() * 100) if samples.size else None
    inf_percent = float(np.isinf(samples).mean() * 100) if samples.size else None
    samples = samples[np.isfinite(samples)]
    if not samples.size:
        return [0, nan_percent, inf_percent, *([None] * 7)]
    p05, median, p95 = np.percentile(samples, [5, 50, 95])
    return [int(samples.size), nan_percent, inf_percent, float(samples.mean()), float(samples.std(ddof=0)), float(samples.min()),
            float(p05), float(median), float(p95), float(samples.max())]
