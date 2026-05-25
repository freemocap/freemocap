//! Outlier rejection via weighted subset-ensemble triangulation.
//!
//! When the all-cameras DLT triangulation has high reprojection error,
//! this algorithm tries subsets of cameras (dropping up to `max_drop` cameras)
//! and combines the results in a weighted ensemble. The weight for each
//! subset is `exp(-K * error / target)`, strongly favoring low-error subsets.
//!
//! This is a port of the Python outlier rejection in
//! `freemocap/core/tasks/triangulation/helpers/outlier_rejection.py`.

use nalgebra::Matrix3x4;

use super::dlt;

/// Default configuration for outlier rejection.
#[derive(Debug, Clone)]
pub struct OutlierRejectionConfig {
    /// Minimum number of cameras needed to triangulate a point.
    pub min_cameras: usize,
    /// Maximum number of cameras to drop in the subset search.
    pub max_cameras_to_drop: usize,
    /// Target mean reprojection error in normalized coords.
    /// Drives `exp(-K * error / target)` weighting.
    pub target_reprojection_error: f64,
    /// Weight decay constant (K in the exponential).
    pub weight_decay_k: f64,
}

impl Default for OutlierRejectionConfig {
    fn default() -> Self {
        Self {
            min_cameras: 2,
            max_cameras_to_drop: 2,
            target_reprojection_error: 0.02,
            weight_decay_k: 5.0,
        }
    }
}

/// Result of triangulating a single point with outlier rejection.
#[derive(Debug, Clone)]
pub struct TriangulationResult {
    /// The 3D point (ensemble-weighted or best-subset).
    pub point_3d: [f64; 3],
    /// Per-camera weights, normalized to sum to 1.0.
    pub camera_weights: Vec<f64>,
    /// Mean reprojection error of the returned point.
    pub mean_error: f64,
    /// Whether the all-cameras result passed the target threshold
    /// (no subset search was needed).
    pub used_all_cameras: bool,
}

/// Triangulate a single point with outlier rejection.
///
/// # Arguments
/// * `points` — N camera observations in normalized coords.
/// * `extrinsics` — N camera [R|t] matrices (must match `points` length).
/// * `config` — Outlier rejection parameters.
///
/// Returns `None` if fewer than `min_cameras` observations are provided,
/// or if all triangulation attempts fail.
pub fn triangulate_with_outlier_rejection(
    points: &[[f64; 2]],
    extrinsics: &[Matrix3x4<f64>],
    config: &OutlierRejectionConfig,
) -> Option<TriangulationResult> {
    let n = points.len();
    if n < config.min_cameras {
        return None;
    }

    // ── Baseline: triangulate with all cameras ──
    let default_p3d = dlt::triangulate_simple(points, extrinsics)?;

    // Compute per-camera reprojection errors
    let mut default_errors = vec![0.0f64; n];
    let mut sum_err = 0.0;
    for i in 0..n {
        default_errors[i] = dlt::reprojection_error(&points[i], &default_p3d, &extrinsics[i])
            .unwrap_or(f64::MAX);
        sum_err += default_errors[i];
    }
    let default_mean_error = sum_err / n as f64;

    // ── Early exit: error already below target ──
    if default_mean_error < config.target_reprojection_error {
        return Some(TriangulationResult {
            point_3d: default_p3d,
            camera_weights: vec![1.0 / n as f64; n],
            mean_error: default_mean_error,
            used_all_cameras: true,
        });
    }

    // ── Subset search ─────────────────────────────────────────────────
    let default_weight =
        (-config.weight_decay_k * default_mean_error / config.target_reprojection_error).exp();

    // Ensemble accumulators
    let mut weighted_sum = [default_weight * default_p3d[0],
                            default_weight * default_p3d[1],
                            default_weight * default_p3d[2]];
    let mut total_weight = default_weight;
    let mut camera_weights = vec![default_weight; n];
    let mut best_p3d = default_p3d;
    let mut best_error = default_mean_error;

    for drop_count in 1..=config.max_cameras_to_drop {
        let selected_count = n - drop_count;
        if selected_count < config.min_cameras {
            break;
        }

        let mut level_best_error = f64::MAX;
        let mut level_best_p3d = default_p3d;

        // Iterate all combinations of `selected_count` cameras
        let indices: Vec<usize> = (0..n).collect();
        for combo in combinations(&indices, selected_count) {
            let subset_pts: Vec<[f64; 2]> = combo.iter().map(|&i| points[i]).collect();
            let subset_ext: Vec<Matrix3x4<f64>> = combo.iter().map(|&i| extrinsics[i]).collect();

            let candidate = match dlt::triangulate_simple(&subset_pts, &subset_ext) {
                Some(p) => p,
                None => continue,
            };

            // Reprojection error for this subset
            let mut sum_e = 0.0;
            let mut valid = 0;
            for &i in &combo {
                if let Some(e) = dlt::reprojection_error(&points[i], &candidate, &extrinsics[i]) {
                    sum_e += e;
                    valid += 1;
                }
            }
            if valid == 0 { continue; }
            let mean_e = sum_e / valid as f64;

            let weight = (-config.weight_decay_k * mean_e / config.target_reprojection_error).exp();

            // Accumulate into ensemble
            weighted_sum[0] += weight * candidate[0];
            weighted_sum[1] += weight * candidate[1];
            weighted_sum[2] += weight * candidate[2];
            total_weight += weight;
            for &i in &combo {
                camera_weights[i] += weight;
            }

            if mean_e < level_best_error {
                level_best_error = mean_e;
                level_best_p3d = candidate;
            }
        }

        if level_best_error < best_error {
            best_error = level_best_error;
            best_p3d = level_best_p3d;
        }

        // Early exit if we found a good enough subset
        if best_error < config.target_reprojection_error {
            break;
        }
    }

    // ── Finalize ensemble ──
    let point_3d = if total_weight > 1e-12 {
        [weighted_sum[0] / total_weight,
         weighted_sum[1] / total_weight,
         weighted_sum[2] / total_weight]
    } else {
        best_p3d
    };

    // Normalize camera weights
    if total_weight > 1e-12 {
        for w in &mut camera_weights {
            *w /= total_weight;
        }
    } else {
        // Fallback: weight 1.0 for cameras in the best subset, 0 for others
        // (best subset is not tracked — just use uniform)
        camera_weights.fill(1.0 / n as f64);
    }

    Some(TriangulationResult {
        point_3d,
        camera_weights,
        mean_error: best_error,
        used_all_cameras: false,
    })
}

/// Generate all k-combinations from a slice of indices.
fn combinations(indices: &[usize], k: usize) -> Vec<Vec<usize>> {
    if k == 0 { return vec![vec![]]; }
    if indices.is_empty() || k > indices.len() { return vec![]; }

    let mut result = Vec::new();
    let first = indices[0];
    let rest = &indices[1..];

    // Combos that include `first`
    for mut combo in combinations(rest, k - 1) {
        combo.insert(0, first);
        result.push(combo);
    }
    // Combos that exclude `first`
    result.extend(combinations(rest, k));

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_combinations() {
        let result = combinations(&[0, 1, 2], 2);
        assert_eq!(result.len(), 3);
        // [[0,1], [0,2], [1,2]]
    }
}
