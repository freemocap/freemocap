//! End-to-end test: VideoGroup → FrameSlots → full pipeline topology → triangulated 3D output.
//!
//! Uses the new `VideoGroup` API (with dispatcher thread and `FrameSlots` output)
//! to feed synchronized video frames into the real-time pipeline. The pipeline
//! distributor consumes `FrameSlots` identically to the live CameraGroup path —
//! zero code changes in the pipeline itself.
//!
//! This test validates the complete chain: video file → dispatcher → FrameSlots →
//! distributor → camera nodes → aggregator → triangulated 3D points.

#[cfg(test)]
mod tests {
    use std::path::Path;
    use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
    use std::sync::{mpsc, Arc, Mutex, RwLock};
    use std::time::Instant;

    use skellycam::camera_group::sync_utils::BreakableBarrier;
    use skellycam::camera_group::FrameSlots;
    use skellytracker::trackers::charuco::CharucoTracker;

    use crate::pipeline::aggregator::{self, Aggregator};
    use crate::pipeline::camera_node::{self, CameraNode};
    use crate::pipeline::distributor::{self, Distributor, PipelineCommand};
    use crate::pipeline::types::DistributorSlot;
    use crate::triangulation::calibration_loader;
    use crate::triangulation::outlier_rejection::OutlierRejectionConfig;
    use crate::video_reader::VideoGroup;

    const TEST_BASE: &str =
        r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data";
    const CALIB_PATH: &str =
        r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\freemocap_test_data_camera_calibration.toml";
    const MAX_REPROJECTION_ERROR_PX: f64 = 60.0;
    const MAX_FRAMES: usize = 30;

    /// Full E2E: VideoGroup dispatcher feeds FrameSlots → pipeline processes →
    /// triangulated 3D output. The pipeline distributor consumes FrameSlots
    /// exactly as it would from a live CameraGroup.
    #[test]
    fn test_realtime_pipeline_with_video_group() {
        crate::init_logging("freemocap=debug,skellycam=info,info");

        let calib_path = Path::new(CALIB_PATH);
        if !calib_path.exists() {
            tracing::warn!("Skipping — calibration TOML not found at {}", CALIB_PATH);
            return;
        }

        // ── Pacing signal: shared between dispatcher and distributor ────────
        let pacing_signal = Arc::new(AtomicI64::new(-1));

        // ── Open synchronized videos via new VideoGroup API ──────────────────
        let videos = [
            format!("{}/synchronized_videos/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", TEST_BASE),
            format!("{}/synchronized_videos/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", TEST_BASE),
            format!("{}/synchronized_videos/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", TEST_BASE),
        ];
        let cam_ids = ["Cam1".to_string(), "Cam2".to_string(), "Cam3".to_string()];

        // Skip if test data not available
        if !Path::new(&videos[0]).exists() {
            tracing::warn!("Skipping — test videos not found");
            return;
        }

        let mut video_group =
            VideoGroup::open(&videos, &cam_ids).expect("Failed to open video group");
        let n_cameras = video_group.n_cameras();
        let n_frames = video_group.frame_count();

        // ── Start dispatcher (paced, limited frames for test) ────────────────
        video_group
            .start(Some(pacing_signal.clone()), Some(MAX_FRAMES))
            .expect("Failed to start video dispatcher");
        let frame_slots = video_group.frame_slots();
        let video_ts_slot = video_group.video_timestamps_slot_arc();

        tracing::info!(
            "[freemocap::test] VideoGroup started: {} cameras, {} frames (test limit: {})",
            n_cameras, n_frames, MAX_FRAMES,
        );

        // ── Load calibration ─────────────────────────────────────────────────
        let camera_models = calibration_loader::load_calibration(calib_path)
            .expect("Failed to load calibration TOML");
        assert_eq!(camera_models.len(), 3, "Expected 3 cameras in calibration");

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
        let output_slot: Arc<Mutex<Option<crate::pipeline::types::AggregatorOutput>>> =
            Arc::new(Mutex::new(None));
        let shutdown_flag = Arc::new(AtomicBool::new(false));

        // ── Channels ─────────────────────────────────────────────────────────
        let (dist_cmd_tx, dist_cmd_rx) = mpsc::channel();

        let mut cam_output_txs = Vec::with_capacity(n_cameras);
        let mut cam_rxs_for_agg: Vec<(String, mpsc::Receiver<crate::pipeline::types::CameraNodeOutput>)> =
            Vec::with_capacity(n_cameras);

        for i in 0..n_cameras {
            let (tx, rx) = mpsc::channel();
            cam_output_txs.push(tx);
            cam_rxs_for_agg.push((cam_ids[i].clone(), rx));
        }

        let (agg_cmd_tx, agg_cmd_rx) = mpsc::channel();
        let dist_slot_for_agg = distributor_slot.clone();

        // ── Spawn distributor (with video_timestamps_slot) ────────────────────
        let dist = Distributor::new(
            barrier.clone(),
            distributor_slot.clone(),
            dist_cmd_rx,
            frame_slots,
            Some(video_ts_slot),
            Some(pacing_signal),
            shutdown_flag.clone(),
        );

        let dist_handle = std::thread::Builder::new()
            .name("freemocap-distributor".into())
            .spawn(move || distributor::run_distributor(dist))
            .expect("Failed to spawn distributor");

        // ── Spawn camera nodes ────────────────────────────────────────────────
        let mut cam_handles = Vec::with_capacity(n_cameras);
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

        // ── Spawn aggregator ─────────────────────────────────────────────────
        let agg = Aggregator {
            camera_rxs: cam_rxs_for_agg,
            cmd_rx: agg_cmd_rx,
            output_slot: output_slot.clone(),
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

        tracing::info!("[freemocap::test] all pipeline threads spawned");

        // ═══════════════════════════════════════════════════════════════════════
        // Collect results while the pipeline runs autonomously.
        // The dispatcher feeds frames → distributor polls → camera nodes detect →
        // aggregator triangulates → output_slot updated.
        // ═══════════════════════════════════════════════════════════════════════

        let mut total_frames_processed = 0usize;
        let mut total_triangulated_points = 0usize;
        let mut all_3d_points: Vec<[f64; 3]> = Vec::new();
        let mut last_frame_seen: i64 = -1;
        let collect_start = Instant::now();

        // Poll output_slot until either:
        // - We've seen all expected frames
        // - Timeout (60s)
        // - VideoGroup dispatcher exits (is_alive → false) and output stops
        let timeout = std::time::Duration::from_secs(60);
        let mut idle_checks = 0u32;
        const MAX_IDLE_CHECKS: u32 = 100; // 1 second at 10ms sleep

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

            // Exit conditions
            if total_frames_processed >= MAX_FRAMES {
                tracing::info!(
                    "[freemocap::test] all {} expected frames processed",
                    MAX_FRAMES
                );
                break;
            }

            if collect_start.elapsed() > timeout {
                tracing::warn!("[freemocap::test] timeout waiting for pipeline output");
                break;
            }

            // If dispatcher has exited and no new frames for a while, we're done
            if !video_group.is_alive() {
                idle_checks += 1;
                if idle_checks > MAX_IDLE_CHECKS {
                    tracing::info!(
                        "[freemocap::test] dispatcher exited, {} frames processed",
                        total_frames_processed
                    );
                    break;
                }
            }

            std::thread::sleep(std::time::Duration::from_millis(10));
        }

        let collect_elapsed = collect_start.elapsed();

        // ── Shutdown pipeline ────────────────────────────────────────────────
        shutdown_flag.store(true, Ordering::SeqCst);
        barrier.break_barrier();
        drop(dist_cmd_tx);
        drop(agg_cmd_tx);
        drop(cam_cmd_txs);
        drop(cam_output_txs);
        let _ = dist_handle.join();
        for h in cam_handles {
            let _ = h.join();
        }
        let _ = agg_handle.join();
        video_group.shutdown();

        // ═══════════════════════════════════════════════════════════════════════
        // Verify results
        // ═══════════════════════════════════════════════════════════════════════

        tracing::info!(
            "\n=== E2E Pipeline Test Results ===\n\
             Frames processed:         {}\n\
             Total triangulated 3D:    {}\n\
             Throughput:               {:.1} fps\n\
             Wall time:                {:.1}s\n\
             ==============================",
            total_frames_processed,
            total_triangulated_points,
            total_frames_processed as f64 / collect_elapsed.as_secs_f64(),
            collect_elapsed.as_secs_f64(),
        );

        assert!(
            total_frames_processed > 0,
            "Should have processed at least some frames"
        );
        assert!(
            total_triangulated_points > 0,
            "Should have triangulated at least some 3D points"
        );

        // Scale validation (from known test data: ~2100mm mean distance)
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

            assert!(
                scale > 500.0,
                "Scale too small ({:.1} mm) — triangulation may be using wrong units",
                scale
            );
            assert!(
                scale < 10000.0,
                "Scale too large ({:.1} mm) — check calibration format",
                scale
            );
        }
    }
}
