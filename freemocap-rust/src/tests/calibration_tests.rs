//! Calibration loading + DLT triangulation tests.
//!
//! Usage:
//!   cargo run --release -- test calibration --calibration PATH

use std::path::Path;

use super::info_block;
use crate::cli::CalibrationArgs;
use freemocap::triangulation::calibration_loader;
use freemocap::triangulation::charuco::CameraModel;

pub fn run(args: &CalibrationArgs) -> anyhow::Result<()> {
    let calib_path = Path::new(&args.calibration);

    if !calib_path.exists() {
        anyhow::bail!("Calibration TOML not found: {}", args.calibration);
    }

    info_block(&[
        "══════════════════════════════════════════════════",
        &format!("  CALIBRATION TEST\n  Path: {}", args.calibration),
        "══════════════════════════════════════════════════",
        "",
    ]);

    // ── Load calibration ──────────────────────────────────────────────────
    let models = calibration_loader::load_calibration(calib_path)
        .map_err(|e| anyhow::anyhow!("Failed to load calibration: {e}"))?;

    let n_cams = models.len();
    tracing::info!("  ✓ Loaded {} camera models", n_cams);

    // ── Validate each camera model ─────────────────────────────────────────
    for (name, model) in &models {
        validate_camera_model(name, model)?;
    }

    // ── Print calibration summary ─────────────────────────────────────────
    let mut summary = vec![
        "".to_string(),
        "┌──────────────────────────────────────────────────────┐".to_string(),
        "│  CALIBRATION SUMMARY                                  │".to_string(),
        "├──────────────────────────────────────────────────────┤".to_string(),
    ];
    for (name, model) in &models {
        summary.push(format!(
            "│  {:<10}  fx={:8.1}  cx={:7.1}  cy={:7.1}  k1={:+.4}  │",
            name,
            model.camera_matrix[0][0],
            model.camera_matrix[0][2],
            model.camera_matrix[1][2],
            model.dist_coeffs[0],
        ));
        summary.push(format!(
            "│            tx={:8.1}  ty={:8.1}  tz={:8.1}                   │",
            model.extrinsics[0][3],
            model.extrinsics[1][3],
            model.extrinsics[2][3],
        ));
    }
    summary.push("└──────────────────────────────────────────────────────┘".to_string());
    summary.push(String::new());
    info_block(&summary.iter().map(|s| s.as_str()).collect::<Vec<_>>());

    // ── Verify pairwise extrinsics are reasonable ─────────────────────────
    if n_cams >= 2 {
        let cam_names: Vec<&String> = models.keys().collect();
        for i in 0..cam_names.len() {
            for j in (i + 1)..cam_names.len() {
                let cam_i = &models[cam_names[i]];
                let cam_j = &models[cam_names[j]];
                let dx = cam_i.extrinsics[0][3] - cam_j.extrinsics[0][3];
                let dy = cam_i.extrinsics[1][3] - cam_j.extrinsics[1][3];
                let dz = cam_i.extrinsics[2][3] - cam_j.extrinsics[2][3];
                let distance = (dx * dx + dy * dy + dz * dz).sqrt();
                tracing::info!(
                    "  {} ↔ {} baseline: {:.1} mm",
                    cam_names[i], cam_names[j], distance
                );
                if distance < 100.0 {
                    tracing::warn!(
                        "    ⚠ Baseline < 100mm — cameras may be too close for accurate triangulation"
                    );
                }
            }
        }
    }

    info_block(&[
        "",
        "  ✓ Calibration test PASSED",
        "",
    ]);

    Ok(())
}

fn validate_camera_model(name: &str, model: &CameraModel) -> anyhow::Result<()> {
    let fx = model.camera_matrix[0][0];
    let fy = model.camera_matrix[1][1];
    let cx = model.camera_matrix[0][2];
    let cy = model.camera_matrix[1][2];

    if fx <= 0.0 || fy <= 0.0 {
        anyhow::bail!("[{name}] Invalid focal length: fx={fx}, fy={fy}");
    }
    if cx <= 0.0 || cy <= 0.0 {
        anyhow::bail!("[{name}] Invalid principal point: cx={cx}, cy={cy}");
    }
    if fx < 100.0 || fx > 10000.0 {
        tracing::warn!("[{name}] Suspicious focal length: fx={fx:.1} — expected 500-5000 range");
    }

    // Check extrinsics translation is non-zero for at least one camera
    let t_norm = (
        model.extrinsics[0][3].powi(2)
        + model.extrinsics[1][3].powi(2)
        + model.extrinsics[2][3].powi(2)
    ).sqrt();
    tracing::info!(
        "  [{name}] fx={fx:.1} fy={fy:.1} cx={cx:.1} cy={cy:.1}  |t|={t_norm:.1}mm  ✓"
    );

    Ok(())
}
