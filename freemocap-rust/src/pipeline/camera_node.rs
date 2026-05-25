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
use super::types::{CameraNodeOutput, CameraPipelineTimestamps, DistributorSlot};

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
/// Each cycle:
/// 1. Check for commands (config update, shutdown)
/// 2. Wait at barrier (distributor has written new frame)
/// 3. Read this camera's JPEG + skellycam timestamps from the shared slot
/// 4. Decode JPEG → BGR
/// 5. Run charuco detection
/// 6. Send CameraNodeOutput to aggregator
///
/// All timestamps are nanoseconds since T=0 (process start) using
/// skellycam's performance clock.
pub fn run_camera_node(node: CameraNode, mut detector: CharucoTracker) {
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
            break;
        }

        // ── Read frame + skellycam timestamps from shared slot ──
        let (frame_number, jpeg_bytes, skellycam_timestamps) = {
            let slot = node.slot.read().unwrap();
            let frame_data = slot
                .per_camera_data
                .iter()
                .find(|d| d.camera_id == node.camera_id)
                .cloned();
            match frame_data {
                Some(data) => (slot.frame_number, data.jpeg_bytes, data.skellycam_timestamps),
                None => {
                    eprintln!(
                        "[freemocap] CameraNode[{}]: no frame data in slot",
                        node.camera_id
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
                eprintln!(
                    "[freemocap] CameraNode[{}]: JPEG decode error: {:?}",
                    node.camera_id, e
                );
                continue;
            }
        };

        let camera_post_jpeg_decode_ns = performance_counter_nanoseconds();

        // ── Charuco detection ──
        let observation = detector.detect(frame_number as u64, &image);

        let camera_post_detection_ns = performance_counter_nanoseconds();

        // ── Assemble output with full timestamp chain ──
        let camera_pre_send_ns = performance_counter_nanoseconds();

        let output = CameraNodeOutput {
            camera_id: node.camera_id.clone(),
            frame_number,
            charuco_observation: Some(Box::new(observation)),
            timestamps: CameraPipelineTimestamps {
                skellycam: skellycam_timestamps,
                camera_dequeue_ns,
                camera_post_jpeg_decode_ns,
                camera_post_detection_ns,
                camera_pre_send_ns,
            },
        };

        if node.output_tx.send(output).is_err() {
            break;
        }
    }
}
