//! Direct Linear Transform (DLT) triangulation.
//!
//! Operates on undistorted-normalized 2D coordinates (intrinsics already removed).
//! All camera coordinates are in the normalized image plane: (x, y) = (X_cam/Z_cam, Y_cam/Z_cam).
//!
//! Reference: Hartley & Zisserman, Multiple View Geometry, 2nd ed., §12.2

use nalgebra::{Matrix3x4, SVD, Vector4, U4};

/// Triangulate a single 3D point from N ≥ 2 normalized camera observations.
///
/// # Arguments
/// * `points` — N observations as `[(x_norm, y_norm)]` in normalized image coords.
/// * `extrinsics` — N camera matrices as `[R|t]` (3x4). Must be same length as `points`.
///
/// Returns `[X, Y, Z]` in world coordinates, or `None` if the SVD fails.
pub fn triangulate_simple(points: &[[f64; 2]], extrinsics: &[Matrix3x4<f64>]) -> Option<[f64; 3]> {
    assert_eq!(points.len(), extrinsics.len());
    let n = points.len();
    if n < 2 {
        return None;
    }

    // Build the A matrix: 2N rows × 4 columns
    // For each camera i with [R|t]_i and observation (x, y):
    //   row 2i   = x * r3 - r1
    //   row 2i+1 = y * r3 - r2
    let mut a = nalgebra::DMatrix::<f64>::zeros(2 * n, 4);

    for i in 0..n {
        let x = points[i][0];
        let y = points[i][1];
        let m = &extrinsics[i]; // 3x4

        let r1 = m.row(0);
        let r2 = m.row(1);
        let r3 = m.row(2);

        for j in 0..4 {
            a[(2 * i, j)] = x * r3[j] - r1[j];
            a[(2 * i + 1, j)] = y * r3[j] - r2[j];
        }
    }

    // Solve A * X = 0 via SVD. The solution is the right singular vector
    // corresponding to the smallest singular value.
    let svd = SVD::new(a, true, true);
    let v = svd.v_t?;         // V^T: 4×4, rows are right singular vectors
    let solution = v.row(3);  // last row = smallest singular value

    let w = solution[3];
    if w.abs() < 1e-12 {
        return None;
    }

    Some([solution[0] / w, solution[1] / w, solution[2] / w])
}

/// Project a 3D world point into a camera's normalized image plane.
///
/// Returns `(x_norm, y_norm)` = `(X_cam/Z_cam, Y_cam/Z_cam)`, or `None`
/// if the point is behind the camera (Z_cam ≤ 0).
pub fn project_to_camera(point_3d: &[f64; 3], extrinsics: &Matrix3x4<f64>) -> Option<[f64; 2]> {
    let hom = Vector4::new(point_3d[0], point_3d[1], point_3d[2], 1.0);
    let projected = extrinsics * hom; // 3-vector: [X_cam, Y_cam, Z_cam]

    let z = projected[2];
    if z <= 1e-12 {
        return None; // behind camera
    }
    Some([projected[0] / z, projected[1] / z])
}

/// Compute reprojection error (Euclidean distance) in normalized coords.
pub fn reprojection_error(observed: &[f64; 2], point_3d: &[f64; 3], extrinsics: &Matrix3x4<f64>) -> Option<f64> {
    let projected = project_to_camera(point_3d, extrinsics)?;
    let dx = observed[0] - projected[0];
    let dy = observed[1] - projected[1];
    Some((dx * dx + dy * dy).sqrt())
}

#[cfg(test)]
mod tests {
    use super::*;
    use nalgebra::Matrix3x4;

    /// Two synthetic cameras: one at origin looking along +Z, one shifted right.
    fn synthetic_extrinsics() -> Vec<Matrix3x4<f64>> {
        vec![
            // Camera 0: identity [R=I | t=0]
            Matrix3x4::new(
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
            ),
            // Camera 1: shifted 1m to the right, looking parallel
            // R=I, t=[-1, 0, 0] (camera is at x=+1 in world)
            Matrix3x4::new(
                1.0, 0.0, 0.0, -1.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
            ),
        ]
    }

    #[test]
    fn test_triangulate_simple_perfect() {
        let extrinsics = synthetic_extrinsics();
        // Point at (0, 0, 5) in world. In camera 0: (0/5, 0/5) = (0, 0).
        // In camera 1: world pt (0,0,5), cam at (1,0,0): cam coord = (-1, 0, 5) → (-0.2, 0).
        let points = vec![[0.0, 0.0], [-0.2, 0.0]];
        let result = triangulate_simple(&points, &extrinsics);
        assert!(result.is_some());
        let p = result.unwrap();
        assert!((p[0] - 0.0).abs() < 1e-6, "x={}", p[0]);
        assert!((p[1] - 0.0).abs() < 1e-6, "y={}", p[1]);
        assert!((p[2] - 5.0).abs() < 1e-6, "z={}", p[2]);
    }

    #[test]
    fn test_project_to_camera() {
        let ext = Matrix3x4::new(
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
        );
        let p3d = [0.0, 0.0, 5.0];
        let proj = project_to_camera(&p3d, &ext);
        assert!(proj.is_some());
        let (x, y) = (proj.unwrap()[0], proj.unwrap()[1]);
        assert!((x - 0.0).abs() < 1e-12);
        assert!((y - 0.0).abs() < 1e-12);
    }

    #[test]
    fn test_triangulate_simple_with_noise() {
        // Same setup but add a tiny bit of noise to observations
        let extrinsics = synthetic_extrinsics();
        let points = vec![[0.001, -0.001], [-0.199, 0.001]];
        let result = triangulate_simple(&points, &extrinsics);
        assert!(result.is_some());
        let p = result.unwrap();
        assert!((p[2] - 5.0).abs() < 0.1, "z={}", p[2]);
    }
}
