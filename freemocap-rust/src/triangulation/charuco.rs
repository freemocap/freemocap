//! Charuco corner triangulation with manual undistortion.
//!
//! Undistorts pixel observations using the Brown-Conrady model (iterative
//! inverse), groups corners by ID across cameras, and triangulates 3D points
//! via DLT with outlier rejection.

use std::collections::HashMap;

use nalgebra::Matrix3x4;

use super::outlier_rejection::{self, OutlierRejectionConfig};

/// Minimal camera model for triangulation.
#[derive(Debug, Clone)]
pub struct CameraModel {
    pub camera_id: String,
    /// 3x3 intrinsics: [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
    pub camera_matrix: [[f64; 3]; 3],
    /// Distortion: [k1, k2, p1, p2]
    pub dist_coeffs: [f64; 4],
    /// 3x4 extrinsics: [R | t]
    pub extrinsics: [[f64; 4]; 3],
}

impl CameraModel {
    /// Extrinsics as nalgebra Matrix3x4.
    pub fn extrinsics_na(&self) -> Matrix3x4<f64> {
        Matrix3x4::new(
            self.extrinsics[0][0], self.extrinsics[0][1], self.extrinsics[0][2], self.extrinsics[0][3],
            self.extrinsics[1][0], self.extrinsics[1][1], self.extrinsics[1][2], self.extrinsics[1][3],
            self.extrinsics[2][0], self.extrinsics[2][1], self.extrinsics[2][2], self.extrinsics[2][3],
        )
    }

    /// Undistort pixel coordinates → normalized image coordinates.
    ///
    /// Uses iterative inverse of the Brown-Conrady distortion model.
    /// Typically converges in 2-3 iterations for k1 ≈ -0.3.
    pub fn undistort_pixel(&self, px: f64, py: f64) -> [f64; 2] {
        let fx = self.camera_matrix[0][0];
        let fy = self.camera_matrix[1][1];
        let cx = self.camera_matrix[0][2];
        let cy = self.camera_matrix[1][2];
        let k1 = self.dist_coeffs[0];
        let k2 = self.dist_coeffs[1];
        let p1 = self.dist_coeffs[2];
        let p2 = self.dist_coeffs[3];

        // Pixel → distorted-normalized
        let xd = (px - cx) / fx;
        let yd = (py - cy) / fy;

        // Iterative inverse: start with distorted as initial guess
        let mut x = xd;
        let mut y = yd;

        for _ in 0..5 {
            let r2 = x * x + y * y;
            let r4 = r2 * r2;
            let radial = 1.0 + k1 * r2 + k2 * r4;
            let dx_tang = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x);
            let dy_tang = p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y;

            // Forward distortion: (x, y) → (xd_computed, yd_computed)
            let xd_computed = x * radial + dx_tang;
            let yd_computed = y * radial + dy_tang;

            // Correction
            x += xd - xd_computed;
            y += yd - yd_computed;

            // Early exit
            let err = (xd - xd_computed).abs() + (yd - yd_computed).abs();
            if err < 1e-10 {
                break;
            }
        }

        [x, y]
    }

    /// Project 3D point through full model (extrinsics → distortion → pixels).
    /// Returns pixel coordinates or None if behind camera.
    pub fn project_3d_to_pixel(&self, point_3d: &[f64; 3]) -> Option<[f64; 2]> {
        let ext = self.extrinsics_na();
        let hom = nalgebra::Vector4::new(point_3d[0], point_3d[1], point_3d[2], 1.0);
        let cam = ext * hom;
        let z = cam[2];
        if z <= 1e-12 {
            return None;
        }

        let xn = cam[0] / z;
        let yn = cam[1] / z;

        let fx = self.camera_matrix[0][0];
        let fy = self.camera_matrix[1][1];
        let cx = self.camera_matrix[0][2];
        let cy = self.camera_matrix[1][2];
        let k1 = self.dist_coeffs[0];
        let k2 = self.dist_coeffs[1];
        let p1 = self.dist_coeffs[2];
        let p2 = self.dist_coeffs[3];

        // Forward distortion
        let r2 = xn * xn + yn * yn;
        let r4 = r2 * r2;
        let radial = 1.0 + k1 * r2 + k2 * r4;
        let dx = 2.0 * p1 * xn * yn + p2 * (r2 + 2.0 * xn * xn);
        let dy = p1 * (r2 + 2.0 * yn * yn) + 2.0 * p2 * xn * yn;

        let xd = xn * radial + dx;
        let yd = yn * radial + dy;

        Some([fx * xd + cx, fy * yd + cy])
    }
}

/// Triangulate charuco corners observed across multiple cameras.
///
/// # Arguments
/// * `corner_observations` — per camera: Vec of `(corner_id, pixel_x, pixel_y)`.
/// * `camera_models` — calibration data keyed by camera_id.
/// * `rejection_config` — outlier rejection parameters.
/// * `max_reprojection_error_px` — pixel-space rejection threshold.
///
/// Returns a map from corner_id to `[x, y, z]` world coordinates.
pub fn triangulate_charuco_corners(
    corner_observations: &HashMap<String, Vec<(i32, f64, f64)>>,
    camera_models: &HashMap<String, CameraModel>,
    rejection_config: &OutlierRejectionConfig,
    max_reprojection_error_px: f64,
) -> HashMap<i32, [f64; 3]> {
    // ── Group by corner ID across cameras ──
    let mut corner_group: HashMap<i32, Vec<(String, f64, f64)>> = HashMap::new();
    for (cam_id, obs) in corner_observations {
        for &(corner_id, px, py) in obs {
            corner_group.entry(corner_id).or_default().push((cam_id.clone(), px, py));
        }
    }

    let mut result = HashMap::new();

    for (&corner_id, observations) in &corner_group {
        if observations.len() < 2 {
            continue;
        }

        // ── Undistort pixel → normalized per camera ──
        let mut normalized_points: Vec<[f64; 2]> = Vec::with_capacity(observations.len());
        let mut valid_extrinsics: Vec<Matrix3x4<f64>> = Vec::with_capacity(observations.len());
        let mut valid_cam_ids: Vec<String> = Vec::with_capacity(observations.len());
        let mut valid_pixels: Vec<(f64, f64)> = Vec::with_capacity(observations.len());

        for (cam_id, px, py) in observations {
            let model = match camera_models.get(cam_id) {
                Some(m) => m,
                None => continue,
            };
            let norm = model.undistort_pixel(*px, *py);
            normalized_points.push(norm);
            valid_extrinsics.push(model.extrinsics_na());
            valid_cam_ids.push(cam_id.clone());
            valid_pixels.push((*px, *py));
        }

        if normalized_points.len() < 2 {
            continue;
        }

        // ── Triangulate with outlier rejection (normalized coords) ──
        let tri_result = match outlier_rejection::triangulate_with_outlier_rejection(
            &normalized_points,
            &valid_extrinsics,
            rejection_config,
        ) {
            Some(r) => r,
            None => continue,
        };

        // ── Pixel-space reprojection gate ──
        let mut pixel_error_sum = 0.0f64;
        let mut pixel_error_count = 0;
        for i in 0..valid_cam_ids.len() {
            let model = &camera_models[&valid_cam_ids[i]];
            if let Some(proj_px) = model.project_3d_to_pixel(&tri_result.point_3d) {
                let (orig_px, orig_py) = valid_pixels[i];
                let err = ((proj_px[0] - orig_px).powi(2) + (proj_px[1] - orig_py).powi(2)).sqrt();
                pixel_error_sum += err;
                pixel_error_count += 1;
            }
        }

        if pixel_error_count > 0 {
            let mean_pixel_error = pixel_error_sum / pixel_error_count as f64;
            if mean_pixel_error > max_reprojection_error_px {
                continue;
            }
        }

        result.insert(corner_id, tri_result.point_3d);
    }

    result
}
