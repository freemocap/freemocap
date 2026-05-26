//! Load anipose-format camera calibration from TOML files.

use std::collections::HashMap;
use std::path::Path;

use super::charuco::CameraModel;

/// Parse an anipose calibration TOML file into camera models.
pub fn load_calibration(path: &Path) -> Result<HashMap<String, CameraModel>, String> {
    let content = std::fs::read_to_string(path)
        .map_err(|e| format!("Failed to read calibration file: {e}"))?;

    let toml_value: toml::Value = toml::from_str(&content)
        .map_err(|e| format!("Failed to parse TOML: {e}"))?;

    let table = toml_value.as_table()
        .ok_or("TOML root is not a table")?;

    let mut models = HashMap::new();

    for (key, value) in table {
        if key == "metadata" {
            continue; // skip metadata section
        }

        let cam_table = value.as_table()
            .ok_or_else(|| format!("[{key}] is not a table"))?;

        let get = |field: &str| -> Result<&toml::Value, String> {
            cam_table.get(field)
                .ok_or_else(|| format!("[{key}] missing field '{field}'"))
        };

        let get_arr3 = |field: &str| -> Result<[f64; 3], String> {
            let arr = get(field)?.as_array()
                .ok_or_else(|| format!("[{key}].{field} is not an array"))?;
            Ok([
                arr[0].as_float().unwrap_or(0.0),
                arr[1].as_float().unwrap_or(0.0),
                arr[2].as_float().unwrap_or(0.0),
            ])
        };

        let name = get("name")?.as_str().unwrap_or(key).to_string();
        // size is [height, width] — 2-element array, not 3
        let size_arr = get("size")?.as_array()
            .ok_or_else(|| format!("[{key}].size is not an array"))?;
        let _height = size_arr[0].as_float().unwrap_or(0.0) as u32;
        let _width = size_arr[1].as_float().unwrap_or(0.0) as u32;

        // Parse 3x3 camera matrix
        let matrix = get("matrix")?.as_array()
            .ok_or_else(|| format!("[{key}].matrix is not an array"))?;
        let camera_matrix: [[f64; 3]; 3] = [
            [
                matrix[0].as_array().unwrap()[0].as_float().unwrap(),
                matrix[0].as_array().unwrap()[1].as_float().unwrap(),
                matrix[0].as_array().unwrap()[2].as_float().unwrap(),
            ],
            [
                matrix[1].as_array().unwrap()[0].as_float().unwrap(),
                matrix[1].as_array().unwrap()[1].as_float().unwrap(),
                matrix[1].as_array().unwrap()[2].as_float().unwrap(),
            ],
            [
                matrix[2].as_array().unwrap()[0].as_float().unwrap(),
                matrix[2].as_array().unwrap()[1].as_float().unwrap(),
                matrix[2].as_array().unwrap()[2].as_float().unwrap(),
            ],
        ];

        // Parse distortion coefficients (5-element: k1,k2,p1,p2,k3 — ignore k3)
        let distortions = get("distortions")?.as_array()
            .ok_or_else(|| format!("[{key}].distortions is not an array"))?;
        let dist_coeffs: [f64; 4] = [
            distortions[0].as_float().unwrap_or(0.0),
            distortions[1].as_float().unwrap_or(0.0),
            distortions[2].as_float().unwrap_or(0.0),
            distortions[3].as_float().unwrap_or(0.0),
        ];

        // Parse rotation (Rodrigues vector) and translation
        let rotation = get_arr3("rotation")?;
        let translation = get_arr3("translation")?;

        // Convert Rodrigues vector to 3x3 rotation matrix
        let rot_mat = rodrigues_to_matrix(&rotation);

        // Build 3x4 extrinsics: [R | t]
        let extrinsics: [[f64; 4]; 3] = [
            [rot_mat[0][0], rot_mat[0][1], rot_mat[0][2], translation[0]],
            [rot_mat[1][0], rot_mat[1][1], rot_mat[1][2], translation[1]],
            [rot_mat[2][0], rot_mat[2][1], rot_mat[2][2], translation[2]],
        ];

        models.insert(name.clone(), CameraModel {
            camera_id: name,
            camera_matrix,
            dist_coeffs,
            extrinsics,
        });
    }

    Ok(models)
}

/// Convert Rodrigues rotation vector to 3x3 rotation matrix.
/// Uses OpenCV-compatible Rodrigues formula: R = I + sin(θ)/θ * K + (1-cos(θ))/θ² * K²
fn rodrigues_to_matrix(r: &[f64; 3]) -> [[f64; 3]; 3] {
    let theta = (r[0]*r[0] + r[1]*r[1] + r[2]*r[2]).sqrt();

    if theta < 1e-12 {
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
    }

    let ux = r[0] / theta;
    let uy = r[1] / theta;
    let uz = r[2] / theta;

    let k = [
        [0.0, -uz, uy],
        [uz, 0.0, -ux],
        [-uy, ux, 0.0],
    ];

    let sin_t = theta.sin();
    let cos_t = theta.cos();

    let mut r_mat = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            r_mat[i][j] = if i == j { 1.0 } else { 0.0 }
                + sin_t * k[i][j]
                + (1.0 - cos_t) * {
                    let mut sum = 0.0;
                    for m in 0..3 { sum += k[i][m] * k[m][j]; }
                    sum
                };
        }
    }
    r_mat
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_calibration() {
        let path = Path::new(
            r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\freemocap_test_data_camera_calibration.toml"
        );
        if path.exists() {
            let models = load_calibration(path).expect("Failed to load calibration");
            assert_eq!(models.len(), 3);
            assert!(models.contains_key("Cam1"));
            assert!(models.contains_key("Cam2"));
            assert!(models.contains_key("Cam3"));

            let cam1 = &models["Cam1"];
            println!("Cam1 fx={:.1}, cx={:.1}, cy={:.1}, k1={:.3}",
                cam1.camera_matrix[0][0], cam1.camera_matrix[0][2], cam1.camera_matrix[1][2], cam1.dist_coeffs[0]);
            println!("Cam1 extrinsics translation: {:?}", [
                cam1.extrinsics[0][3], cam1.extrinsics[1][3], cam1.extrinsics[2][3]
            ]);

            let cam2 = &models["Cam2"];
            println!("Cam2 extrinsics translation: {:?}", [
                cam2.extrinsics[0][3], cam2.extrinsics[1][3], cam2.extrinsics[2][3]
            ]);
        }
    }
}
