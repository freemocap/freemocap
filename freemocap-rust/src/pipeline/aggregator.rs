use std::collections::HashMap;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::{self, Receiver},
    Arc, Mutex,
};

use skellycam::timestamps::performance::performance_counter_nanoseconds;

use crate::filtering::{OneEuroFilter, RealtimePointGate};
use crate::triangulation::charuco::{triangulate_charuco_corners, CameraModel};
use crate::triangulation::outlier_rejection::OutlierRejectionConfig;

use super::config::PipelineConfig;
use super::distributor::PipelineCommand;
use super::types::{AggregatorOutput, CameraNodeOutput, PipelineTimestamps};

/// State for the aggregator thread.
pub struct Aggregator {
    /// Per-camera input channels — one per camera node.
    pub camera_rxs: Vec<(String, Receiver<CameraNodeOutput>)>,
    pub cmd_rx: Receiver<PipelineCommand>,
    /// Output slot polled by Python websocket relay.
    pub output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    pub shutdown_flag: Arc<AtomicBool>,
    /// Shared distributor slot — read to extract frontend payload bytes
    /// and distributor timestamps for the output.
    pub distributor_slot: Arc<std::sync::RwLock<super::types::DistributorSlot>>,
    /// Camera calibration models keyed by camera_id.
    /// None if calibration hasn't been loaded yet.
    pub calibration: Option<HashMap<String, CameraModel>>,
    /// Whether triangulation is enabled. When false, raw_keypoints
    /// stays empty (2D-only pipeline).
    pub triangulation_enabled: bool,
    /// Configuration for the outlier rejection algorithm.
    pub rejection_config: OutlierRejectionConfig,
    /// Maximum mean reprojection error in pixels. Points exceeding
    /// this after triangulation are rejected (set to NaN).
    pub max_reprojection_error_px: f64,
}

pub fn run_aggregator(agg: Aggregator) {
    let mut config = PipelineConfig::default();
    let mut keypoint_filter = OneEuroFilter::new(
        config.filter_config.min_cutoff,
        config.filter_config.beta,
        config.filter_config.d_cutoff,
    );
    let mut velocity_gate = RealtimePointGate::new(
        config.filter_config.max_velocity_m_per_s,
        config.filter_config.max_rejected_streak,
    );

    loop {
        // ── Handle commands ──
        match agg.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(new_config)) => {
                keypoint_filter.set_params(
                    new_config.filter_config.min_cutoff,
                    new_config.filter_config.beta,
                    new_config.filter_config.d_cutoff,
                );
                velocity_gate.set_max_velocity(new_config.filter_config.max_velocity_m_per_s);
                velocity_gate.set_max_streak(new_config.filter_config.max_rejected_streak);
                config = new_config;
            }
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if agg.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Collect outputs from all camera nodes ──
        // Blocks on each camera's channel. Camera nodes always send in
        // steady state. On shutdown, barrier.break_barrier() releases
        // camera nodes, which drop their Senders, disconnecting these
        // channels and causing recv() to return Err.
        let aggregator_collection_start_ns = performance_counter_nanoseconds();

        let mut camera_outputs: Vec<CameraNodeOutput> =
            Vec::with_capacity(agg.camera_rxs.len());
        let mut expected_frame: Option<i64> = None;

        for (_cam_id, rx) in &agg.camera_rxs {
            match rx.recv() {
                Ok(output) => {
                    if let Some(ef) = expected_frame {
                        if output.frame_number != ef {
                            tracing::warn!(
                                "[freemocap::aggregator] frame mismatch: expected {} got {} from {}",
                                ef, output.frame_number, output.camera_id
                            );
                            camera_outputs.clear();
                            break;
                        }
                    } else {
                        expected_frame = Some(output.frame_number);
                    }
                    camera_outputs.push(output);
                }
                Err(_) => {
                    // Channel disconnected — camera node shut down
                    camera_outputs.clear();
                    break;
                }
            }
        }

        if camera_outputs.len() != agg.camera_rxs.len() {
            break;
        }

        let frame_number = expected_frame.unwrap();
        let aggregator_all_received_ns = performance_counter_nanoseconds();

        // ── Triangulate charuco observations ──
        let raw_keypoints = if agg.triangulation_enabled {
            if let Some(ref calibration) = agg.calibration {
                let mut corner_obs: HashMap<String, Vec<(i32, f64, f64)>> = HashMap::new();
                for output in &camera_outputs {
                    if let Some(ref obs) = output.charuco_observation {
                        let corners: Vec<(i32, f64, f64)> = obs
                            .detected_charuco_corner_ids
                            .iter()
                            .zip(obs.detected_charuco_corners_image_coordinates.iter())
                            .map(|(&id, pt)| (id, pt[0], pt[1]))
                            .collect();
                        if !corners.is_empty() {
                            corner_obs.insert(output.camera_id.clone(), corners);
                        }
                    }
                }
                if corner_obs.len() >= 2 {
                    let tri_result = triangulate_charuco_corners(
                        &corner_obs,
                        calibration,
                        &agg.rejection_config,
                        agg.max_reprojection_error_px,
                    );
                    tracing::trace!(
                        "[freemocap::aggregator] frame={} cameras_with_detections={} triangulated_points={}",
                        frame_number,
                        corner_obs.len(),
                        tri_result.len(),
                    );
                    tri_result
                        .into_iter()
                        .map(|(id, xyz)| (id.to_string(), xyz))
                        .collect()
                } else {
                    tracing::trace!(
                        "[freemocap::aggregator] frame={} only {} cameras with detections (need ≥2)",
                        frame_number,
                        corner_obs.len(),
                    );
                    HashMap::new()
                }
            } else {
                tracing::trace!(
                    "[freemocap::aggregator] frame={} triangulation enabled but no calibration loaded",
                    frame_number,
                );
                HashMap::new()
            }
        } else {
            HashMap::new()
        };

        let aggregator_post_triangulation_ns = performance_counter_nanoseconds();

        // ── Velocity gate ──
        let t_sec = performance_counter_nanoseconds() as f64 * 1e-9;
        let gated = if config.filter_config.filter_enabled {
            velocity_gate.gate(t_sec, &raw_keypoints)
        } else {
            raw_keypoints.clone()
        };

        // ── One Euro filter ──
        let filtered = if config.filter_config.filter_enabled {
            keypoint_filter.filter(t_sec, &gated)
        } else {
            gated
        };

        let aggregator_post_filter_ns = performance_counter_nanoseconds();

        tracing::debug!(
            "[freemocap::aggregator] frame={} n_cameras={} triangulated={} total_us={}",
            frame_number,
            camera_outputs.len(),
            raw_keypoints.len(),
            (aggregator_post_filter_ns - aggregator_collection_start_ns) / 1000,
        );

        // ── Extract frontend payload + distributor timestamps from slot ──
        let (frontend_payload_bytes, timestamp_ns, camera_fps, distributor_timestamps) = {
            let slot = agg.distributor_slot.read().unwrap();
            (
                slot.frontend_payload_bytes.clone(),
                slot.timestamp_ns,
                slot.camera_fps,
                slot.distributor_timestamps.clone(),
            )
        };

        // ── Publish output ──
        let output = AggregatorOutput {
            frame_number,
            camera_outputs,
            keypoints_raw: raw_keypoints,
            keypoints_filtered: filtered,
            frontend_payload_bytes,
            timestamp_ns,
            camera_fps,
            pipeline_timestamps: PipelineTimestamps {
                distributor_slot_write_ns: distributor_timestamps.distributor_slot_write_ns,
                distributor_barrier_release_ns: distributor_timestamps
                    .distributor_barrier_release_ns,
                aggregator_collection_start_ns,
                aggregator_all_received_ns,
                aggregator_post_triangulation_ns,
                aggregator_post_filter_ns,
                aggregator_output_published_ns: performance_counter_nanoseconds(),
            },
        };

        *agg.output_slot.lock().unwrap() = Some(output);
    }

    tracing::info!("[freemocap::aggregator] shutting down");
}
