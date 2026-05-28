//! Charuco detection performance test — runs on test video frames.
//!
//! Usage:
//!   cargo run --release -- test charuco [--data-dir PATH] [--max-frames N]

use std::path::Path;

use skellytracker::trackers::charuco::CharucoTracker;

use super::info_block;
use crate::cli::{self, CharucoArgs};
use freemocap::video_reader::reader::VideoReader;

pub fn run(args: &CharucoArgs) -> anyhow::Result<()> {
    let data_dir = cli::resolve_data_dir(&args.data_dir);
    let video_dir = cli::resolve_video_dir(&data_dir);

    let video_path = format!(
        "{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4",
        video_dir
    );

    if !Path::new(&video_path).exists() {
        anyhow::bail!("Test video not found: {}", video_path);
    }

    let max_frames = args.max_frames;

    info_block(&[
        "══════════════════════════════════════════════════",
        &format!("  CHARUCO DETECTION TEST\n  Video: {}\n  Max frames: {max_frames}", video_path),
        "══════════════════════════════════════════════════",
        "",
    ]);

    // ── Open video ────────────────────────────────────────────────────────
    let mut reader = VideoReader::open(&video_path)
        .map_err(|e| anyhow::anyhow!("Failed to open video: {e}"))?;

    tracing::info!(
        "  ✓ Opened video: {}x{} @ {:.1} fps, {} frames",
        reader.width(),
        reader.height(),
        reader.fps(),
        reader.frame_count(),
    );

    // ── Create detector ───────────────────────────────────────────────────
    let detector = CharucoTracker::new(7, 5, 30.0, 0.75, 2)
        .map_err(|e| anyhow::anyhow!("Failed to create CharucoTracker: {e}"))?;

    tracing::info!("  ✓ Detector created (7x5 board, 30mm squares, DICT_4X4_250)");

    // ── Run detection on N frames ─────────────────────────────────────────
    let mut detect_times_ms: Vec<f64> = Vec::with_capacity(max_frames);
    let mut corner_counts: Vec<usize> = Vec::with_capacity(max_frames);

    for i in 0..max_frames {
        let frame = reader
            .read_next()
            .ok_or_else(|| anyhow::anyhow!("EOF at frame {i}"))?
            .map_err(|e| anyhow::anyhow!("Read error at frame {i}: {e}"))?;

        let t0 = std::time::Instant::now();
        let observation = detector.detect(i as u64, &frame);
        let elapsed = t0.elapsed().as_secs_f64() * 1000.0;

        let n_corners = observation.detected_charuco_corner_ids.len();
        detect_times_ms.push(elapsed);
        corner_counts.push(n_corners);

        if i % 5 == 0 || i == max_frames - 1 {
            tracing::debug!(
                "  frame {:3}: {:5} corners in {:6.1}ms",
                i, n_corners, elapsed
            );
        }
    }

    // ── Statistics ────────────────────────────────────────────────────────
    detect_times_ms.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median_ms = detect_times_ms[detect_times_ms.len() / 2];
    let mean_ms = detect_times_ms.iter().sum::<f64>() / detect_times_ms.len() as f64;
    let min_ms = detect_times_ms[0];
    let max_ms = detect_times_ms[detect_times_ms.len() - 1];

    let total_corners: usize = corner_counts.iter().sum();
    let median_corners = {
        let mut c = corner_counts.clone();
        c.sort();
        c[c.len() / 2]
    };

    info_block(&[
        "",
        &format!("┌──────────────────────────────────────────────────────┐"),
        &format!("│  CHARUCO DETECTION — {max_frames} frames                               │"),
        &format!("├──────────────────────────────────────────────────────┤"),
        &format!("│  Detection time:  median {:6.1}ms  mean {:6.1}ms          │", median_ms, mean_ms),
        &format!("│                    min {:6.1}ms  max {:6.1}ms          │", min_ms, max_ms),
        &format!("│  Total corners:   {}  (median {median_corners}/frame)                      │", total_corners),
        &format!("│  Estimated FPS (detection only): {:.0}                       │", 1000.0 / median_ms),
        &format!("└──────────────────────────────────────────────────────┘"),
        "",
    ]);

    if total_corners == 0 {
        tracing::warn!("  ⚠ No charuco corners detected — check board config (7x5, 30mm, DICT_4X4_250)");
    }

    Ok(())
}
