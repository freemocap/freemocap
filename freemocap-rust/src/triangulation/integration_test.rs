//! Integration test: triangulate charuco observations from test data.

#[cfg(test)]
mod tests {
    use std::collections::HashMap;
    use std::path::Path;

    use serde::Deserialize;

    use crate::triangulation::calibration_loader;
    use crate::triangulation::charuco::triangulate_charuco_corners;
    use crate::triangulation::outlier_rejection::OutlierRejectionConfig;

    #[derive(Debug, Deserialize)]
    struct CharucoEntry {
        camera_name: String,
        frame_index: i64,
        corners: Vec<CharucoCorner>,
    }

    #[derive(Debug, Deserialize)]
    struct CharucoCorner {
        corner_id: i32,
        pixel_xy: [f64; 2],
    }

    #[test]
    fn test_triangulate_from_real_data() {
        let data_dir = Path::new(
            r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data"
        );

        let calib_path = data_dir.join("freemocap_test_data_camera_calibration.toml");
        let obs_path = data_dir.join("output_data").join("charuco_observations.json");

        if !calib_path.exists() || !obs_path.exists() {
            eprintln!("Test data not found — skipping integration test");
            return;
        }

        // ── Load calibration ──
        let camera_models = calibration_loader::load_calibration(&calib_path)
            .expect("Failed to load calibration");

        assert_eq!(camera_models.len(), 3, "Expected 3 cameras");

        // ── Load observations ──
        let json_str = std::fs::read_to_string(&obs_path)
            .expect("Failed to read observations JSON");
        let observations: Vec<CharucoEntry> = serde_json::from_str(&json_str)
            .expect("Failed to parse observations JSON");

        println!("Loaded {} observation entries", observations.len());

        // ── Group observations by frame ──
        let mut frames: HashMap<i64, HashMap<String, Vec<(i32, f64, f64)>>> = HashMap::new();
        for entry in &observations {
            let corners: Vec<(i32, f64, f64)> = entry.corners.iter()
                .map(|c| (c.corner_id, c.pixel_xy[0], c.pixel_xy[1]))
                .collect();
            if !corners.is_empty() {
                frames.entry(entry.frame_index)
                    .or_default()
                    .insert(entry.camera_name.clone(), corners);
            }
        }

        println!("Grouped into {} frames", frames.len());

        // ── Triangulate each frame ──
        let rejection_config = OutlierRejectionConfig::default();
        let max_reprojection_error_px = 60.0; // match Python default

        let mut total_points = 0usize;
        let mut all_points: Vec<[f64; 3]> = Vec::new();

        let mut frame_indices: Vec<_> = frames.keys().copied().collect();
        frame_indices.sort();

        for &frame_idx in &frame_indices {
            let frame_obs = &frames[&frame_idx];

            // Only triangulate frames with ≥2 cameras observing
            if frame_obs.len() < 2 {
                continue;
            }

            let result = triangulate_charuco_corners(
                frame_obs,
                &camera_models,
                &rejection_config,
                max_reprojection_error_px,
            );

            total_points += result.len();
            all_points.extend(result.values().copied());
        }

        println!("\n=== Results ===");
        println!("Total triangulated 3D points: {}", total_points);
        println!("Unique frames with triangulation: {}", {
            let mut count = 0;
            for frame_idx in &frame_indices {
                if frames[frame_idx].len() >= 2 {
                    count += 1;
                }
            }
            count
        });

        if total_points > 0 {
            // Compute statistics
            let n = all_points.len() as f64;
            let mut sum_x = 0.0f64;
            let mut sum_y = 0.0f64;
            let mut sum_z = 0.0f64;
            let mut min_x = f64::MAX;
            let mut max_x = f64::MIN;
            let mut min_y = f64::MAX;
            let mut max_y = f64::MIN;
            let mut min_z = f64::MAX;
            let mut max_z = f64::MIN;

            for p in &all_points {
                sum_x += p[0];
                sum_y += p[1];
                sum_z += p[2];
                min_x = min_x.min(p[0]);
                max_x = max_x.max(p[0]);
                min_y = min_y.min(p[1]);
                max_y = max_y.max(p[1]);
                min_z = min_z.min(p[2]);
                max_z = max_z.max(p[2]);
            }

            let mean = [sum_x / n, sum_y / n, sum_z / n];
            let range = [max_x - min_x, max_y - min_y, max_z - min_z];

            println!("\n=== 3D Point Statistics (mm) ===");
            println!("Mean: [{:.1}, {:.1}, {:.1}]", mean[0], mean[1], mean[2]);
            println!("Range: [{:.1}, {:.1}, {:.1}]", range[0], range[1], range[2]);
            println!("Min: [{:.1}, {:.1}, {:.1}]", min_x, min_y, min_z);
            println!("Max: [{:.1}, {:.1}, {:.1}]", max_x, max_y, max_z);

            // Check scale: should be in the 2000-3000mm range (2-3m)
            let scale = (mean[0].powi(2) + mean[1].powi(2) + mean[2].powi(2)).sqrt();
            println!("\nMean distance from origin: {:.1} mm", scale);

            assert!(total_points > 0, "Should have triangulated at least some points");
            assert!(scale > 500.0, "Scale should be >500mm (was {:.1})", scale);
            assert!(scale < 10000.0, "Scale should be <10000mm (was {:.1})", scale);
        }
    }
}
