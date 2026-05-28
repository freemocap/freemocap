//! End-to-end pipeline test: VideoGroup → distributor → camera nodes → aggregator.
//!
//! Usage:
//!   cargo run --release -- test pipeline [--data-dir PATH] [--calibration PATH] [--max-frames N]

use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex, RwLock};
use std::time::Instant;

use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellytracker::trackers::charuco::CharucoTracker;

use super::info_block;
use crate::cli::{self, PipelineArgs};
use freemocap::pipeline::aggregator::{self, Aggregator};
use freemocap::pipeline::camera_node::{self, CameraNode};
use freemocap::pipeline::distributor::{self, Distributor, PipelineCommand};
use freemocap::pipeline::stats::{self, PipelineStats, print_pipeline_stats};
use freemocap::pipeline::types::DistributorSlot;
use freemocap::triangulation::calibration_loader;
use freemocap::triangulation::charuco::CameraModel;
use freemocap::triangulation::outlier_rejection::OutlierRejectionConfig;
use freemocap::video_reader::VideoGroup;

const MAX_REPROJECTION_ERROR_PX: f64 = 60.0;

pub fn run(args: &PipelineArgs) -> anyhow::Result<()> {
    let data_dir = cli::resolve_data_dir(&args.data_dir);
    let calib_path_str = cli::resolve_calibration_path(&args.calibration, &data_dir);
    let video_dir = cli::resolve_video_dir(&data_dir);

    let calib_path = Path::new(&calib_path_str);
    if !calib_path.exists() {
        anyhow::bail!("Calibration TOML not found: {}", calib_path_str);
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
    let n_cameras = 3;

    info_block(&[
        "══════════════════════════════════════════════════════════════",
        &format!("  E2E PIPELINE TEST"),
        &format!("  Data:      {data_dir}"),
        &format!("  Videos:    {video_dir}"),
        &format!("  Max frames: {max_frames}"),
        "══════════════════════════════════════════════════════════════",
        "",
    ]);

    // ── Load calibration ─────────────────────────────────────────────────
    let camera_models: HashMap<String, CameraModel> =
        calibration_loader::load_calibration(calib_path)
            .map_err(|e| anyhow::anyhow!("Failed to load calibration: {e}"))?;
    assert_eq!(camera_models.len(), 3, "Expected 3 cameras in calibration");

    tracing::info!("  ✓ Loaded calibration for {} cameras", camera_models.len());

    // ── Open VideoGroup ───────────────────────────────────────────────────
    let dispatcher_stats_out = Arc::new(Mutex::new(None));

    let mut video_group =
        VideoGroup::open(&videos, &cam_ids)
            .map_err(|e| anyhow::anyhow!("Failed to open video group: {e}"))?;

    video_group
        .start(Some(max_frames), dispatcher_stats_out.clone())
        .map_err(|e| anyhow::anyhow!("Failed to start video dispatcher: {e}"))?;

    let video_rx = video_group
        .take_video_receiver()
        .ok_or_else(|| anyhow::anyhow!("No video receiver"))?;
    let video_ts_slot = video_group.video_timestamps_slot_arc();

    tracing::info!(
        "  ✓ VideoGroup started: {} cameras, {} frames",
        video_group.n_cameras(),
        video_group.frame_count(),
    );

    // ── Pipeline topology ─────────────────────────────────────────────────
    let barrier = Arc::new(BreakableBarrier::new(n_cameras + 1));
    let distributor_slot: Arc<RwLock<DistributorSlot>> =
        Arc::new(RwLock::new(DistributorSlot {
            frame_number: -1,
            per_camera_data: Vec::new(),
            frontend_payload_bytes: Vec::new(),
            timestamp_ns: 0.0,
            camera_fps: 0.0,
            distributor_timestamps: Default::default(),
        }));
    let output_slot: Arc<Mutex<Option<freemocap::pipeline::types::AggregatorOutput>>> =
        Arc::new(Mutex::new(None));
    let shutdown_flag = Arc::new(AtomicBool::new(false));

    // ── Channels ──────────────────────────────────────────────────────────
    let (dist_cmd_tx, dist_cmd_rx) = mpsc::channel();

    let mut cam_output_txs = Vec::with_capacity(n_cameras);
    let mut cam_rxs_for_agg: Vec<(String, mpsc::Receiver<freemocap::pipeline::types::CameraNodeOutput>)> =
        Vec::with_capacity(n_cameras);

    for i in 0..n_cameras {
        let (tx, rx) = mpsc::channel();
        cam_output_txs.push(tx);
        cam_rxs_for_agg.push((cam_ids[i].clone(), rx));
    }

    let (agg_cmd_tx, agg_cmd_rx) = mpsc::channel();
    let dist_slot_for_agg = distributor_slot.clone();

    // ── Spawn distributor ─────────────────────────────────────────────────
    let dummy_slots = skellycam::camera_group::FrameSlots {
        raw_frames: Arc::new(Mutex::new(None)),
        frontend_payload: Arc::new(Mutex::new(None)),
    };

    let dist = Distributor::new(
        barrier.clone(),
        distributor_slot.clone(),
        dist_cmd_rx,
        dummy_slots,
        Some(video_ts_slot),
        None,
        Some(video_rx),
        shutdown_flag.clone(),
    );

    let dist_handle = std::thread::Builder::new()
        .name("freemocap-distributor".into())
        .spawn(move || distributor::run_distributor(dist))
        .expect("Failed to spawn distributor");

    // ── Spawn camera nodes ────────────────────────────────────────────────
    let mut cam_handles: Vec<std::thread::JoinHandle<stats::CameraNodeStats>> =
        Vec::with_capacity(n_cameras);
    let mut cam_cmd_txs: Vec<mpsc::Sender<PipelineCommand>> = Vec::with_capacity(n_cameras);

    for i in 0..n_cameras {
        let (cam_cmd_tx, cam_cmd_rx) = mpsc::channel();
        cam_cmd_txs.push(cam_cmd_tx);

        let node = CameraNode {
            camera_id: cam_ids[i].clone(),
            cmd_rx: cam_cmd_rx,
            output_tx: cam_output_txs[i].clone(),
            barrier: barrier.clone(),
            slot: distributor_slot.clone(),
            shutdown_flag: shutdown_flag.clone(),
        };

        let detector = CharucoTracker::new(7, 5, 30.0, 0.75, 2)
            .expect("Failed to create CharucoTracker");

        let handle = std::thread::Builder::new()
            .name(format!("freemocap-camera-{}", cam_ids[i]))
            .spawn(move || camera_node::run_camera_node(node, detector))
            .expect("Failed to spawn camera node");
        cam_handles.push(handle);
    }

    // ── Spawn aggregator ──────────────────────────────────────────────────
    let agg = Aggregator {
        camera_rxs: cam_rxs_for_agg,
        cmd_rx: agg_cmd_rx,
        output_slot: output_slot.clone(),
        result_ready: Arc::new(AtomicBool::new(false)),
        shutdown_flag: shutdown_flag.clone(),
        distributor_slot: dist_slot_for_agg,
        calibration: Some(camera_models),
        triangulation_enabled: true,
        rejection_config: OutlierRejectionConfig::default(),
        max_reprojection_error_px: MAX_REPROJECTION_ERROR_PX,
    };

    let agg_handle = std::thread::Builder::new()
        .name("freemocap-aggregator".into())
        .spawn(move || aggregator::run_aggregator(agg))
        .expect("Failed to spawn aggregator");

    tracing::info!("  ✓ All pipeline threads spawned (distributor + 3 cameras + aggregator)");

    // ═══════════════════════════════════════════════════════════════════════
    // Collect results
    // ═══════════════════════════════════════════════════════════════════════

    let mut total_frames_processed = 0usize;
    let mut total_triangulated_points = 0usize;
    let mut all_3d_points: Vec<[f64; 3]> = Vec::new();
    let mut last_frame_seen: i64 = -1;
    let collect_start = Instant::now();

    let timeout = std::time::Duration::from_secs(60);
    let mut idle_checks = 0u32;
    const MAX_IDLE_CHECKS: u32 = 100;

    loop {
        let output = output_slot.lock().unwrap().clone();
        if let Some(ref out) = output {
            if out.frame_number > last_frame_seen {
                last_frame_seen = out.frame_number;
                total_frames_processed += 1;
                total_triangulated_points += out.keypoints_raw.len();
                for xyz in out.keypoints_raw.values() {
                    all_3d_points.push(*xyz);
                }
                idle_checks = 0;
            }
        }
        drop(output);

        if total_frames_processed >= max_frames {
            tracing::info!(
                "  ✓ All {max_frames} expected frames processed",
            );
            break;
        }

        if collect_start.elapsed() > timeout {
            tracing::warn!("  ⚠ Timeout waiting for pipeline output");
            break;
        }

        if !video_group.is_alive() {
            idle_checks += 1;
            if idle_checks > MAX_IDLE_CHECKS {
                tracing::info!(
                    "  Dispatcher exited, {} frames processed",
                    total_frames_processed
                );
                break;
            }
        }

        std::thread::sleep(std::time::Duration::from_millis(10));
    }

    let collect_elapsed = collect_start.elapsed();

    // ── Shutdown ──────────────────────────────────────────────────────────
    shutdown_flag.store(true, Ordering::SeqCst);
    barrier.break_barrier();
    drop(dist_cmd_tx);
    drop(agg_cmd_tx);
    drop(cam_cmd_txs);
    drop(cam_output_txs);

    let distributor_stats = dist_handle.join().unwrap_or_default();
    let camera_stats: Vec<stats::CameraNodeStats> =
        cam_handles.into_iter().map(|h| h.join().unwrap_or_default()).collect();
    let aggregator_stats = agg_handle.join().unwrap_or_default();
    video_group.shutdown();
    let dispatcher_stats = dispatcher_stats_out.lock().ok().and_then(|g| g.clone());

    // ── Print pipeline statistics ─────────────────────────────────────────
    let pipeline_stats = PipelineStats {
        n_frames: total_frames_processed,
        wall_time_secs: collect_elapsed.as_secs_f64(),
        dispatcher: dispatcher_stats,
        distributor: distributor_stats,
        cameras: camera_stats,
        aggregator: aggregator_stats,
    };
    print_pipeline_stats(&pipeline_stats);

    // ── Verify results ────────────────────────────────────────────────────
    let fps = total_frames_processed as f64 / collect_elapsed.as_secs_f64();

    tracing::info!(
        "\n=== E2E Pipeline Test Results ===\n\
         Frames processed:         {}\n\
         Total triangulated 3D:    {}\n\
         Throughput:               {:.1} fps\n\
         Wall time:                {:.1}s\n\
         ==============================",
        total_frames_processed,
        total_triangulated_points,
        fps,
        collect_elapsed.as_secs_f64(),
    );

    if total_frames_processed == 0 {
        anyhow::bail!("No frames processed — pipeline did not produce output");
    }
    if total_triangulated_points == 0 {
        anyhow::bail!("No 3D points triangulated — check calibration and charuco detection");
    }

    // Scale validation
    if !all_3d_points.is_empty() {
        let n = all_3d_points.len() as f64;
        let mut sum = [0.0f64; 3];
        for p in &all_3d_points {
            for i in 0..3 {
                sum[i] += p[i];
            }
        }
        let mean = [sum[0] / n, sum[1] / n, sum[2] / n];
        let scale = (mean[0].powi(2) + mean[1].powi(2) + mean[2].powi(2)).sqrt();

        if scale < 500.0 {
            anyhow::bail!("Scale too small ({:.1} mm) — triangulation may be using wrong units", scale);
        }
        if scale > 10000.0 {
            anyhow::bail!("Scale too large ({:.1} mm) — check calibration format", scale);
        }
        tracing::info!("  ✓ Scale validation: {:.1} mm mean distance (expected 500-10000mm)", scale);
    }

    info_block(&[
        "",
        &format!("  ✓ E2E Pipeline test PASSED — {total_triangulated_points} points, {fps:.1} fps"),
        "",
    ]);

    Ok(())
}
