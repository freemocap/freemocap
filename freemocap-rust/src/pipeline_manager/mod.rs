//! PipelineManager: CRUD lifecycle management for real-time pipelines.
//!
//! Each real-time pipeline is bound to a camera group and runs indefinitely,
//! processing live frames through detection and (optionally) triangulation.
//!
//! Responsibilities:
//!   - Creating pipelines (spawning distributor, camera nodes, aggregator threads)
//!   - Returning existing pipelines for already-tracked camera ID sets
//!   - Pushing config updates to running pipelines
//!   - Polling processed frame output
//!   - Orderly shutdown of individual or all pipelines
//!
//! Mirrors skellycam's `CameraGroupManager` pattern: owns a `HashMap<String, T>`
//! keyed by a short UUID, with create/read/update/delete operations.

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex, RwLock};
use std::thread::JoinHandle;

use anyhow::Context;

use crate::pipeline::aggregator::{self, Aggregator};
use crate::pipeline::camera_node::{self, CameraNode};
use crate::pipeline::config::PipelineConfig;
use crate::pipeline::distributor::{self, Distributor, PipelineCommand};
use crate::pipeline::stats::{AggregatorStats, CameraNodeStats, DistributorStats};
use crate::pipeline::types::{AggregatorOutput, CameraNodeOutput, DistributorSlot};
use crate::triangulation::charuco::CameraModel;

use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::camera_group::FrameSlots;
use skellytracker::trackers::charuco::CharucoTracker;

/// A running real-time pipeline attached to a camera group.
pub struct RealtimePipeline {
    pub pipeline_id: String,
    pub group_id: String,
    pub camera_ids: Vec<String>,
    pub config: PipelineConfig,
    pub output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    pub result_ready: Arc<AtomicBool>,
    pub shutdown_flag: Arc<AtomicBool>,
    pub handles: Vec<JoinHandle<()>>,
    cmd_senders: Vec<mpsc::Sender<PipelineCommand>>,
    barrier: Arc<BreakableBarrier>,
    distributor_stats: Arc<Mutex<Option<DistributorStats>>>,
    camera_stats: Arc<Mutex<Vec<CameraNodeStats>>>,
    aggregator_stats: Arc<Mutex<Option<AggregatorStats>>>,
    started_at: std::time::Instant,
}

/// Manages the lifecycle of real-time pipelines.
///
/// Each pipeline is keyed by a unique pipeline ID (6-char UUID prefix).
/// Pipelines are singletons per camera ID set — creating a pipeline for
/// an already-tracked set of cameras returns the existing one with an
/// updated config.
pub struct PipelineManager {
    pipelines: HashMap<String, RealtimePipeline>,
}

impl PipelineManager {
    pub fn new() -> Self {
        Self {
            pipelines: HashMap::new(),
        }
    }

    // ── CRUD ──────────────────────────────────────────────────────────────

    /// Create and start a new real-time pipeline, or return the existing one
    /// if a pipeline for this camera ID set already exists (with updated config).
    pub fn create_pipeline(
        &mut self,
        frame_slots: FrameSlots,
        config: PipelineConfig,
        group_id: &str,
        camera_ids: Vec<String>,
        calibration: Option<HashMap<String, CameraModel>>,
    ) -> anyhow::Result<String> {
        // Return existing pipeline for this camera set (with updated config)
        for pipeline in self.pipelines.values() {
            if sets_eq(&pipeline.camera_ids, &camera_ids) {
                tracing::info!(
                    "[PipelineManager] found existing pipeline [{}] for camera set, updating config",
                    pipeline.pipeline_id
                );
                for sender in &pipeline.cmd_senders {
                    let _ = sender.send(PipelineCommand::UpdateConfig(config.clone()));
                }
                return Ok(pipeline.pipeline_id.clone());
            }
        }

        let n_cameras = camera_ids.len();
        let pipeline_id = uuid::Uuid::new_v4().as_simple().to_string()[..6].to_string();

        let barrier = Arc::new(BreakableBarrier::new(n_cameras + 1));
        let shutdown_flag = Arc::new(AtomicBool::new(false));
        let output_slot: Arc<Mutex<Option<AggregatorOutput>>> = Arc::new(Mutex::new(None));
        let result_ready = Arc::new(AtomicBool::new(false));

        let slot: Arc<RwLock<DistributorSlot>> = Arc::new(RwLock::new(DistributorSlot {
            frame_number: -1,
            per_camera_data: Vec::new(),
            frontend_payload_bytes: Vec::new(),
            timestamp_ns: 0.0,
            camera_fps: 0.0,
            distributor_timestamps: Default::default(),
        }));
        let slot_for_agg = slot.clone();

        let mut cmd_senders: Vec<mpsc::Sender<PipelineCommand>> = Vec::new();

        // ── Distributor thread ──
        let (dist_cmd_tx, dist_cmd_rx) = mpsc::channel();
        cmd_senders.push(dist_cmd_tx);

        let distributor = Distributor::new(
            barrier.clone(),
            slot.clone(),
            dist_cmd_rx,
            frame_slots.clone(),
            None, None, None,
            shutdown_flag.clone(),
        );

        let distributor_stats: Arc<Mutex<Option<DistributorStats>>> =
            Arc::new(Mutex::new(None));
        let dist_stats = distributor_stats.clone();
        let pid_dist = pipeline_id.clone();
        let dist_handle = std::thread::Builder::new()
            .name(format!("freemocap-distributor-{pipeline_id}"))
            .spawn(move || {
                let stats = distributor::run_distributor(distributor);
                if let Ok(mut guard) = dist_stats.lock() {
                    *guard = Some(stats);
                }
                tracing::info!("[PipelineManager] distributor thread for '{pid_dist}' exited");
            })
            .context("distributor spawn")?;

        let mut handles: Vec<JoinHandle<()>> = vec![dist_handle];

        // ── Camera node threads ──
        let mut camera_rxs: Vec<(String, mpsc::Receiver<CameraNodeOutput>)> = Vec::new();
        let camera_stats: Arc<Mutex<Vec<CameraNodeStats>>> = Arc::new(Mutex::new(Vec::new()));

        for cam_id in &camera_ids {
            let (cam_cmd_tx, cam_cmd_rx) = mpsc::channel();
            cmd_senders.push(cam_cmd_tx);
            let (cam_out_tx, cam_out_rx) = mpsc::channel();
            camera_rxs.push((cam_id.clone(), cam_out_rx));

            let detector = CharucoTracker::new(
                config.charuco_config.squares_x,
                config.charuco_config.squares_y,
                config.charuco_config.square_length_mm,
                config.charuco_config.marker_length_ratio,
                config.charuco_config.dictionary_enum,
            )
            .map_err(|e| anyhow::anyhow!("CharucoTracker for {cam_id}: {e}"))?;

            let cam_node = CameraNode {
                camera_id: cam_id.clone(),
                cmd_rx: cam_cmd_rx,
                output_tx: cam_out_tx,
                barrier: barrier.clone(),
                slot: slot_for_agg.clone(),
                shutdown_flag: shutdown_flag.clone(),
            };

            let cam_stats = camera_stats.clone();
            let cam_handle = std::thread::Builder::new()
                .name(format!("freemocap-camera-{cam_id}-{pipeline_id}"))
                .spawn(move || {
                    let stats = camera_node::run_camera_node(cam_node, detector);
                    if let Ok(mut guard) = cam_stats.lock() {
                        guard.push(stats);
                    }
                })
                .with_context(|| format!("camera node {cam_id}"))?;

            handles.push(cam_handle);
        }

        // ── Aggregator thread ──
        let (agg_cmd_tx, agg_cmd_rx) = mpsc::channel();
        cmd_senders.push(agg_cmd_tx);

        let has_calibration = calibration.is_some();
        let agg = Aggregator {
            camera_rxs,
            cmd_rx: agg_cmd_rx,
            output_slot: output_slot.clone(),
            result_ready: result_ready.clone(),
            shutdown_flag: shutdown_flag.clone(),
            distributor_slot: slot_for_agg,
            calibration,
            triangulation_enabled: has_calibration,
            rejection_config: Default::default(),
            max_reprojection_error_px: 60.0,
        };

        let aggregator_stats: Arc<Mutex<Option<AggregatorStats>>> =
            Arc::new(Mutex::new(None));
        let agg_stats = aggregator_stats.clone();
        let agg_handle = std::thread::Builder::new()
            .name(format!("freemocap-aggregator-{pipeline_id}"))
            .spawn(move || {
                let stats = aggregator::run_aggregator(agg);
                if let Ok(mut guard) = agg_stats.lock() {
                    *guard = Some(stats);
                }
            })
            .context("aggregator spawn")?;

        handles.push(agg_handle);

        tracing::info!(
            "[PipelineManager] pipeline '{}' started: {} cameras, calib={}",
            pipeline_id, n_cameras, has_calibration
        );

        self.pipelines.insert(
            pipeline_id.clone(),
            RealtimePipeline {
                pipeline_id: pipeline_id.clone(),
                group_id: group_id.to_string(),
                camera_ids,
                config,
                output_slot,
                result_ready,
                shutdown_flag,
                handles,
                cmd_senders,
                barrier,
                distributor_stats,
                camera_stats,
                aggregator_stats,
                started_at: std::time::Instant::now(),
            },
        );

        Ok(pipeline_id)
    }

    /// Return a reference to a pipeline by ID.
    pub fn get(&self, pipeline_id: &str) -> Option<&RealtimePipeline> {
        self.pipelines.get(pipeline_id)
    }

    /// Return all pipeline IDs.
    pub fn list(&self) -> Vec<String> {
        self.pipelines.keys().cloned().collect()
    }

    /// Number of active pipelines.
    pub fn count(&self) -> usize {
        self.pipelines.len()
    }

    // ── Config update ────────────────────────────────────────────────────

    /// Send an updated config to a running pipeline's threads.
    pub fn update_config(
        &self,
        pipeline_id: &str,
        config: PipelineConfig,
    ) -> anyhow::Result<()> {
        let pipeline = self
            .pipelines
            .get(pipeline_id)
            .with_context(|| format!("Pipeline '{}' not found", pipeline_id))?;
        for sender in &pipeline.cmd_senders {
            sender
                .send(PipelineCommand::UpdateConfig(config.clone()))
                .context("config update send")?;
        }
        Ok(())
    }

    // ── Output polling ───────────────────────────────────────────────────

    /// Poll output for a single pipeline. Returns None if no new frame since
    /// `if_newer_than`.
    pub fn get_output(
        &self,
        pipeline_id: &str,
        if_newer_than: i64,
    ) -> Option<AggregatorOutput> {
        let pipeline = self.pipelines.get(pipeline_id)?;
        let guard = pipeline.output_slot.lock().ok()?;
        match guard.as_ref() {
            Some(output) if output.frame_number > if_newer_than => {
                let clone = output.clone();
                pipeline.result_ready.store(false, Ordering::SeqCst);
                Some(clone)
            }
            _ => None,
        }
    }

    /// Poll all pipelines for outputs newer than `if_newer_than`.
    pub fn get_all_outputs(
        &self,
        if_newer_than: i64,
    ) -> Vec<(String, AggregatorOutput)> {
        let mut results = Vec::new();
        for (pid, pipeline) in &self.pipelines {
            let guard = match pipeline.output_slot.lock() {
                Ok(g) => g,
                Err(_) => continue,
            };
            if let Some(ref output) = *guard {
                if output.frame_number > if_newer_than {
                    results.push((pid.clone(), output.clone()));
                    pipeline.result_ready.store(false, Ordering::SeqCst);
                }
            }
        }
        results
    }

    /// Block until any pipeline has a processed frame ready, or timeout.
    pub fn wait_for_any_result_ready(&self, timeout_secs: f64) -> bool {
        if self.pipelines.is_empty() {
            std::thread::sleep(std::time::Duration::from_millis(10));
            return false;
        }
        let deadline =
            std::time::Instant::now() + std::time::Duration::from_secs_f64(timeout_secs);
        let mut backoff_ms: u64 = 1;
        loop {
            for pipeline in self.pipelines.values() {
                if pipeline.result_ready.load(Ordering::SeqCst) {
                    return true;
                }
            }
            if std::time::Instant::now() >= deadline {
                return false;
            }
            std::thread::sleep(std::time::Duration::from_millis(backoff_ms));
            backoff_ms = (backoff_ms * 2).min(50);
        }
    }

    /// Check whether a pipeline is alive (shutdown flag not set).
    pub fn is_alive(&self, pipeline_id: &str) -> bool {
        self.pipelines
            .get(pipeline_id)
            .map(|p| !p.shutdown_flag.load(Ordering::Relaxed))
            .unwrap_or(false)
    }

    /// Return camera IDs for a pipeline.
    pub fn camera_ids(&self, pipeline_id: &str) -> Option<Vec<String>> {
        self.pipelines
            .get(pipeline_id)
            .map(|p| p.camera_ids.clone())
    }

    /// Return the group ID a pipeline is attached to.
    pub fn group_id(&self, pipeline_id: &str) -> Option<&str> {
        self.pipelines
            .get(pipeline_id)
            .map(|p| p.group_id.as_str())
    }

    // ── Shutdown ─────────────────────────────────────────────────────────

    /// Shut down and remove a single pipeline by ID.
    pub fn shutdown_pipeline(&mut self, pipeline_id: &str) -> bool {
        if let Some(state) = self.pipelines.remove(pipeline_id) {
            state.shutdown_flag.store(true, Ordering::SeqCst);
            for sender in &state.cmd_senders {
                let _ = sender.send(PipelineCommand::Shutdown);
            }
            state.barrier.break_barrier();
            for handle in state.handles {
                let _ = handle.join();
            }
            tracing::info!("[PipelineManager] pipeline '{}' shut down", pipeline_id);
            true
        } else {
            false
        }
    }

    /// Shut down and remove all pipelines.
    pub fn shutdown_all(&mut self) {
        let ids: Vec<String> = self.pipelines.keys().cloned().collect();
        for pid in &ids {
            self.shutdown_pipeline(pid);
        }
    }
}

impl Default for PipelineManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for PipelineManager {
    fn drop(&mut self) {
        if !self.pipelines.is_empty() {
            tracing::warn!(
                "[PipelineManager] dropped with {} active pipeline(s) — shutting down",
                self.pipelines.len()
            );
            self.shutdown_all();
        }
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn sets_eq(a: &[String], b: &[String]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut a_sorted: Vec<&String> = a.iter().collect();
    let mut b_sorted: Vec<&String> = b.iter().collect();
    a_sorted.sort();
    b_sorted.sort();
    a_sorted == b_sorted
}