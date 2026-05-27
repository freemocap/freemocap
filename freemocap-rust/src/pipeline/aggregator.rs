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
use super::stats::AggregatorStats;
use super::types::{
    AggregatorOutput, AggregatorTimestamps, CameraNodeOutput, PipelineCycleTimestamps,
};

/// State for the aggregator thread.
pub struct Aggregator {
    pub camera_rxs: Vec<(String, Receiver<CameraNodeOutput>)>,
    pub cmd_rx: Receiver<PipelineCommand>,
    pub output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    pub shutdown_flag: Arc<AtomicBool>,
    pub distributor_slot: Arc<std::sync::RwLock<super::types::DistributorSlot>>,
    pub calibration: Option<HashMap<String, CameraModel>>,
    pub triangulation_enabled: bool,
    pub rejection_config: OutlierRejectionConfig,
    pub max_reprojection_error_px: f64,
}

pub fn run_aggregator(agg: Aggregator) -> AggregatorStats {
    let mut stats = AggregatorStats::default();
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
                    camera_outputs.clear();
                    break;
                }
            }
        }

        if camera_outputs.len() != agg.camera_rxs.len() {
            break;
        }

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
                    let n_points = tri_result.len();
                    tri_result
                        .into_iter()
                        .map(|(id, xyz)| (id.to_string(), xyz))
                        .collect()
                } else {
                    HashMap::new()
                }
            } else {
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

        // ── Extract frontend payload + distributor timestamps ──
        let (frontend_payload_bytes, timestamp_ns, camera_fps, distributor_ts) = {
            let slot = agg.distributor_slot.read().unwrap();
            (
                slot.frontend_payload_bytes.clone(),
                slot.timestamp_ns,
                slot.camera_fps,
                slot.distributor_timestamps.clone(),
            )
        };

        let aggregator_output_published_ns = performance_counter_nanoseconds();

        // ── Build aggregator timestamps ──
        let agg_ts = AggregatorTimestamps {
            collection_start_ns: aggregator_collection_start_ns,
            all_received_ns: aggregator_all_received_ns,
            post_triangulation_ns: aggregator_post_triangulation_ns,
            post_filtering_ns: aggregator_post_filter_ns,
            output_published_ns: aggregator_output_published_ns,
        };

        // ── Build per-camera timestamps map ──
        let camera_ts_map: std::collections::HashMap<String, _> = camera_outputs
            .iter()
            .map(|co| (co.camera_id.clone(), co.timestamps.clone()))
            .collect();

        // ── Build composite cycle timestamps ──
        let cycle_ts = PipelineCycleTimestamps {
            distributor: distributor_ts,
            cameras: camera_ts_map,
            aggregator: agg_ts.clone(),
        };

        // ── Record stats ──
        stats.collection_ns.push(agg_ts.collection_ns() as f64);
        stats.triangulation_ns.push(agg_ts.triangulation_ns() as f64);
        stats.filtering_ns.push(agg_ts.filtering_ns() as f64);
        stats.output_publish_ns.push(agg_ts.output_publish_ns() as f64);
        stats.total_ns.push(agg_ts.total_ns() as f64);
        stats.points_triangulated.push(raw_keypoints.len());

        // ── Publish output ──
        let output = AggregatorOutput {
            frame_number: expected_frame.unwrap(),
            camera_outputs,
            keypoints_raw: raw_keypoints,
            keypoints_filtered: filtered,
            frontend_payload_bytes,
            timestamp_ns,
            camera_fps,
            cycle_timestamps: cycle_ts,
        };

        *agg.output_slot.lock().unwrap() = Some(output);
    }

    tracing::info!(
        "[freemocap::aggregator] shutting down ({} frames)",
        stats.total_ns.len()
    );
    stats
}
