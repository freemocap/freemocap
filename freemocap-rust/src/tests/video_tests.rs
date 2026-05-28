//! Video reader/dispatcher tests.
//!
//! Usage:
//!   cargo run --release -- test video [--data-dir PATH] [--max-frames N]

use std::path::Path;

use super::info_block;
use crate::cli::{self, VideoArgs};
use freemocap::pipeline::stats::VideoDispatcherStats;
use std::sync::{Arc, Mutex};

pub fn run(args: &VideoArgs) -> anyhow::Result<()> {
    let data_dir = cli::resolve_data_dir(&args.data_dir);
    let video_dir = cli::resolve_video_dir(&data_dir);
    let video_path = Path::new(&video_dir);

    if !video_path.exists() {
        anyhow::bail!("Video directory not found: {}", video_dir);
    }

    let videos = [
        format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", video_dir),
        format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", video_dir),
        format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", video_dir),
    ];
    let cam_ids = ["Cam1".to_string(), "Cam2".to_string(), "Cam3".to_string()];

    if !Path::new(&videos[0]).exists() {
        anyhow::bail!("Test videos not found — expected at: {}", videos[0]);
    }

    let max_frames = args.max_frames;

    info_block(&[
        "══════════════════════════════════════════════════",
        &format!("  VIDEO READER/DISPATCHER TEST\n  Directory: {}\n  Max frames: {max_frames}", video_dir),
        "══════════════════════════════════════════════════",
        "",
    ]);

    // ── Open video group ──────────────────────────────────────────────────
    let mut group = freemocap::video_reader::VideoGroup::open(&videos, &cam_ids)
        .map_err(|e| anyhow::anyhow!("Failed to open video group: {e}"))?;

    tracing::info!("  ✓ Opened {} videos, {} frames each", group.n_cameras(), group.frame_count());
    assert_eq!(group.n_cameras(), 3, "Expected 3 cameras");
    assert_eq!(group.frame_count(), 222, "Expected 222 frames");

    // ── Start dispatcher ──────────────────────────────────────────────────
    let stats_out = Arc::new(Mutex::new(None));
    group
        .start(Some(max_frames), stats_out.clone())
        .map_err(|e| anyhow::anyhow!("Failed to start video dispatcher: {e}"))?;

    tracing::info!("  ✓ Dispatcher started, reading frames...");

    // ── Read frames from channel ──────────────────────────────────────────
    let rx = group
        .take_video_receiver()
        .ok_or_else(|| anyhow::anyhow!("No video receiver — dispatcher may not have started"))?;

    let start = std::time::Instant::now();
    let mut frame_count = 0i64;
    let mut total_jpeg_bytes = 0usize;

    while let Ok(payload) = rx.recv() {
        frame_count += 1;
        for frame in &payload.frames {
            total_jpeg_bytes += frame.data.len();
        }
        if frame_count % 10 == 0 {
            let elapsed = start.elapsed().as_secs_f64();
            let fps = frame_count as f64 / elapsed;
            tracing::debug!("  frame {} ({:.1} fps)", frame_count, fps);
        }
        if frame_count >= max_frames as i64 {
            break;
        }
    }

    let elapsed = start.elapsed();
    let fps = frame_count as f64 / elapsed.as_secs_f64();
    tracing::info!(
        "  ✓ Received {} multiframes in {:.1}s ({:.1} fps, {} KB total JPEG)",
        frame_count,
        elapsed.as_secs_f64(),
        fps,
        total_jpeg_bytes / 1024,
    );

    // ── Shutdown ──────────────────────────────────────────────────────────
    group.shutdown();

    // ── Dispatcher stats ──────────────────────────────────────────────────
    if let Ok(guard) = stats_out.lock() {
        if let Some(ref dispatcher_stats) = *guard {
            print_dispatcher_stats(dispatcher_stats, frame_count as usize);
        }
    }

    info_block(&[
        "",
        &format!("  ✓ Video test PASSED ({frame_count} frames, {fps:.1} fps)"),
        "",
    ]);

    Ok(())
}

fn print_dispatcher_stats(stats: &VideoDispatcherStats, n_frames: usize) {
    let med = |v: &[f64]| -> f64 {
        if v.is_empty() { return 0.0; }
        let mut s = v.to_vec();
        s.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        s[s.len() / 2]
    };

    let read_med = med(&stats.read_ns) / 1_000_000.0;
    let encode_med = med(&stats.encode_ns) / 1_000_000.0;
    let total_med = med(&stats.total_ns) / 1_000_000.0;

    tracing::info!(
        "  Dispatcher ({n_frames} frames): read {read_med:.1}ms | encode {encode_med:.1}ms | total {total_med:.1}ms (medians)"
    );
}
