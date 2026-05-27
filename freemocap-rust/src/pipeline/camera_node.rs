use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::{self, Receiver, Sender},
    Arc, RwLock,
};

use opencv::imgcodecs;
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::timestamps::performance::performance_counter_nanoseconds;
use skellytracker::trackers::charuco::CharucoTracker;

use super::distributor::PipelineCommand;
use super::stats::CameraNodeStats;
use super::types::{CameraNodeOutput, CameraNodeTimestamps, DistributorSlot};

/// State for a single camera node thread.
pub struct CameraNode {
    pub camera_id: String,
    pub cmd_rx: Receiver<PipelineCommand>,
    pub output_tx: Sender<CameraNodeOutput>,
    pub barrier: Arc<BreakableBarrier>,
    pub slot: Arc<RwLock<DistributorSlot>>,
    pub shutdown_flag: Arc<AtomicBool>,
}

/// Main loop for a camera node thread.
///
/// Returns per-frame timing statistics for every pipeline stage.
pub fn run_camera_node(node: CameraNode, mut detector: CharucoTracker) -> CameraNodeStats {
    let camera_id = node.camera_id.clone();
    let mut stats = CameraNodeStats {
        camera_id: camera_id.clone(),
        ..Default::default()
    };

    loop {
        // ── Handle commands ──
        match node.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(config)) => {
                if let Ok(new_detector) = CharucoTracker::new(
                    config.charuco_config.squares_x,
                    config.charuco_config.squares_y,
                    config.charuco_config.square_length_mm,
                    config.charuco_config.marker_length_ratio,
                    config.charuco_config.dictionary_enum,
                ) {
                    detector = new_detector;
                }
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if node.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Sync with distributor ──
        if !node.barrier.wait() {
            tracing::info!(
                "[freemocap::camera_node] barrier broken cam={}, shutting down",
                camera_id
            );
            break;
        }

        // ── Read frame + source timestamps from shared slot ──
        let (_frame_number, jpeg_bytes, source_timestamps) = {
            let slot = node.slot.read().unwrap();
            let frame_data = slot
                .per_camera_data
                .iter()
                .find(|d| d.camera_id == camera_id)
                .cloned();
            match frame_data {
                Some(data) => (slot.frame_number, data.jpeg_bytes, data.source_timestamps),
                None => {
                    tracing::warn!(
                        "[freemocap::camera_node] no frame data in slot cam={}",
                        camera_id
                    );
                    continue;
                }
            }
        };

        let camera_dequeue_ns = performance_counter_nanoseconds();

        // ── Decode JPEG → BGR ──
        let image = match imgcodecs::imdecode(
            &opencv::core::Vector::<u8>::from_iter(jpeg_bytes.iter().copied()),
            imgcodecs::IMREAD_COLOR,
        ) {
            Ok(img) => img,
            Err(e) => {
                tracing::warn!(
                    "[freemocap::camera_node] JPEG decode error cam={}: {:?}",
                    camera_id, e
                );
                continue;
            }
        };

        let camera_post_jpeg_decode_ns = performance_counter_nanoseconds();
        let decode_ns = camera_post_jpeg_decode_ns - camera_dequeue_ns;

        // ── Charuco detection ──
        let observation = detector.detect(0, &image);

        let camera_post_detection_ns = performance_counter_nanoseconds();
        let detect_ns = camera_post_detection_ns - camera_post_jpeg_decode_ns;
        let n_detected = observation.detected_charuco_corner_ids.len();

        // ── Assemble output ──
        let camera_pre_send_ns = performance_counter_nanoseconds();
        let total_ns = camera_pre_send_ns - camera_dequeue_ns;

        let output = CameraNodeOutput {
            camera_id: camera_id.clone(),
            frame_number: _frame_number,
            charuco_observation: Some(Box::new(observation)),
            timestamps: CameraNodeTimestamps {
                source: source_timestamps,
                dequeue_ns: camera_dequeue_ns,
                post_jpeg_decode_ns: camera_post_jpeg_decode_ns,
                post_detection_ns: camera_post_detection_ns,
                pre_send_ns: camera_pre_send_ns,
            },
        };

        // ── Record stats ──
        stats.jpeg_decode_ns.push(decode_ns as f64);
        stats.charuco_detect_ns.push(detect_ns as f64);
        stats.total_ns.push(total_ns as f64);
        stats.corners_detected.push(n_detected as u32);

        if node.output_tx.send(output).is_err() {
            tracing::info!(
                "[freemocap::camera_node] aggregator channel closed cam={}, shutting down",
                camera_id
            );
            break;
        }
    }

    tracing::info!(
        "[freemocap::camera_node] shutting down cam={} ({} frames)",
        camera_id,
        stats.total_ns.len(),
    );
    stats
}
