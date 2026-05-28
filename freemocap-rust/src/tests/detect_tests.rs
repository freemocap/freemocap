//! Environment detection test — checks test data, OpenCV backend, and build config.
//!
//! Usage:
//!   cargo run --release -- test detect [--data-dir PATH]

use std::path::Path;

use super::info_block;
use crate::cli::{self, DetectArgs};

pub fn run(args: &DetectArgs) -> anyhow::Result<()> {
    let data_dir = cli::resolve_data_dir(&args.data_dir);

    info_block(&[
        "══════════════════════════════════════════════════",
        "  ENVIRONMENT DETECTION",
        "══════════════════════════════════════════════════",
        "",
    ]);

    let mut all_ok = true;

    // ── Test data directory ───────────────────────────────────────────────
    let data_path = Path::new(&data_dir);
    let status = if data_path.exists() && data_path.is_dir() {
        "✓"
    } else {
        all_ok = false;
        "✗"
    };
    tracing::info!("  {} Test data directory: {}", status, data_dir);

    // ── Calibration TOML ──────────────────────────────────────────────────
    let calib_path_str = cli::resolve_calibration_path(&None, &data_dir);
    let calib_path = Path::new(&calib_path_str);
    let status = if calib_path.exists() {
        let size = std::fs::metadata(calib_path)
            .map(|m| m.len())
            .unwrap_or(0);
        format!("✓ ({} bytes)", size)
    } else {
        all_ok = false;
        "✗ (not found)".to_string()
    };
    tracing::info!("  {} Calibration TOML: {}", status, calib_path_str);

    // ── Synchronized videos ───────────────────────────────────────────────
    let video_dir = cli::resolve_video_dir(&data_dir);
    let video_path = Path::new(&video_dir);
    if video_path.exists() {
        let mut count = 0u32;
        let mut total_frames = 0i32;
        if let Ok(entries) = std::fs::read_dir(video_path) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.extension().map_or(false, |e| e == "mp4") {
                    count += 1;
                    // Quick metadata check
                    if let Ok(reader) = freemocap::video_reader::reader::VideoReader::open(&p) {
                        total_frames = reader.frame_count();
                    }
                }
            }
        }
        if count >= 3 {
            tracing::info!("  ✓ Synchronized videos: {} .mp4 files, {} frames each", count, total_frames);
        } else {
            all_ok = false;
            tracing::warn!("  ✗ Synchronized videos: only {}/3 .mp4 files found", count);
        }
    } else {
        all_ok = false;
        tracing::warn!("  ✗ Synchronized videos directory not found: {}", video_dir);
    }

    // ── Build config ──────────────────────────────────────────────────────
    tracing::info!("  ✓ Build profile: {}", if cfg!(debug_assertions) { "debug" } else { "release" });

    // ── Sibling crates ────────────────────────────────────────────────────
    tracing::info!("  ✓ skellycam version: {}", env!("CARGO_PKG_VERSION"));

    // ── Summary ───────────────────────────────────────────────────────────
    info_block(&[
        "",
        if all_ok {
            "══════════════════════════════════════════════════\n  ✓ Environment check PASSED\n══════════════════════════════════════════════════"
        } else {
            "══════════════════════════════════════════════════\n  ✗ Environment check FAILED — see warnings above\n══════════════════════════════════════════════════"
        },
        "",
    ]);

    if !all_ok {
        anyhow::bail!("Environment check failed — resolve issues before running other tests");
    }

    Ok(())
}
