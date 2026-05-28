use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex, RwLock};
use std::thread::JoinHandle;

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyAny};

use crate::pipeline::aggregator::{self, Aggregator};
use crate::pipeline::camera_node::{self, CameraNode};
use crate::pipeline::config::PipelineConfig;
use crate::pipeline::distributor::{self, Distributor, PipelineCommand};
use crate::pipeline::stats::{
    AggregatorStats, CameraNodeStats, DistributorStats, PipelineStats, print_pipeline_stats,
};
use crate::pipeline::types::{
    AggregatorOutput, CameraNodeOutput, DistributorSlot, DistributorTimestamps,
};
use crate::triangulation::calibration_loader;
use std::collections::HashMap;
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::camera_group::FrameSlots;
use skellycam::pyo3_bridge::py_camera_group_manager::PyO3CameraGroupManager;
use skellytracker::trackers::charuco::CharucoTracker;
use crate::triangulation::charuco::CameraModel;

#[pyclass]
pub struct PyO3Pipeline {
    #[allow(dead_code)]
    group_id: String,
    camera_ids: Vec<String>,
    config: PipelineConfig,
    /// Command senders for all nodes (distributor, N cameras, aggregator).
    cmd_senders: Arc<Mutex<Vec<mpsc::Sender<PipelineCommand>>>>,
    /// Aggregator output slot — polled by Python.
    output_slot: Arc<std::sync::Mutex<Option<AggregatorOutput>>>,
    /// Shutdown flag.
    shutdown_flag: Arc<AtomicBool>,
    /// Barrier — broken on shutdown.
    barrier: Arc<BreakableBarrier>,
    /// Thread handles. Joined on shutdown.
    handles: Mutex<Option<Vec<JoinHandle<()>>>>,
    /// Frame slots from the camera group (held for thread spawning).
    #[allow(dead_code)]
    frame_slots: FrameSlots,
    /// Per-thread stats collected at shutdown (written by threads before exit).
    distributor_stats: Arc<Mutex<Option<DistributorStats>>>,
    camera_stats: Arc<Mutex<Vec<CameraNodeStats>>>,
    aggregator_stats: Arc<Mutex<Option<AggregatorStats>>>,
    /// Calibration models loaded from TOML (None → triangulation disabled).
    calibration: Option<HashMap<String, CameraModel>>,
    /// When start() was called — used for wall-clock elapsed reporting.
    started_at: Mutex<Option<std::time::Instant>>,
}

#[pymethods]
impl PyO3Pipeline {
    #[new]
    #[pyo3(signature = (camera_group_manager, group_id, config_json, camera_ids, calibration_toml_path=None))]
    fn new(
        py: Python<'_>,
        camera_group_manager: Py<PyAny>,
        group_id: String,
        config_json: &str,
        camera_ids: Vec<String>,
        calibration_toml_path: Option<String>,
    ) -> PyResult<Self> {
        let config: PipelineConfig = serde_json::from_str(config_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid pipeline config JSON: {e}"
            ))
        })?;

        // Extract FrameSlots from the skellycam PyO3CameraGroupManager.
        // Borrow the Rust struct from the Python object (no data copies).
        let bound = camera_group_manager.bind(py);
        let cam_bound = bound
            .cast::<PyO3CameraGroupManager>()
            .map_err(|e| {
                pyo3::exceptions::PyTypeError::new_err(format!(
                    "camera_group_manager must be a _skellycam_rust.CameraGroupManager: {e}"
                ))
            })?;
        let frame_slots = cam_bound.borrow().get_frame_slots(&group_id).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "CameraGroup '{}' not found", group_id
            ))
        })?;

        let n_cameras = camera_ids.len();

        // Parse calibration if provided (path-based — minimal Python↔Rust interaction)
        let calibration = match &calibration_toml_path {
            Some(path) => {
                let models = calibration_loader::load_calibration(
                    &std::path::Path::new(path),
                )
                .map_err(|e| {
                    pyo3::exceptions::PyValueError::new_err(format!(
                        "Failed to load calibration TOML from '{}': {e}", path
                    ))
                })?;
                tracing::info!(
                    "[PyO3Pipeline] loaded calibration for {} cameras from '{}'",
                    models.len(), path
                );
                Some(models)
            }
            None => None,
        };

        Ok(PyO3Pipeline {
            group_id,
            camera_ids,
            config,
            cmd_senders: Arc::new(Mutex::new(Vec::new())),
            output_slot: Arc::new(Mutex::new(None)),
            shutdown_flag: Arc::new(AtomicBool::new(false)),
            barrier: Arc::new(BreakableBarrier::new(n_cameras + 1)),
            handles: Mutex::new(None),
            frame_slots,
            distributor_stats: Arc::new(Mutex::new(None)),
            camera_stats: Arc::new(Mutex::new(Vec::new())),
            aggregator_stats: Arc::new(Mutex::new(None)),
            calibration,
            started_at: Mutex::new(None),
        })
    }

    fn start(&mut self, _py: Python<'_>) -> PyResult<()> {
        *self.started_at.lock().unwrap() = Some(std::time::Instant::now());

        let mut handles_guard = self.handles.lock().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {e}"))
        })?;

        if handles_guard.is_some() {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "Pipeline already started",
            ));
        }

        let n_cameras = self.camera_ids.len();
        // Use the barrier created in new() — shutdown()/Drop break self.barrier,
        // so threads must wait on the SAME barrier instance.
        self.barrier.set_total(n_cameras + 1);
        let barrier = self.barrier.clone();
        let slot = Arc::new(RwLock::new(DistributorSlot {
            frame_number: -1,
            per_camera_data: Vec::new(),
            frontend_payload_bytes: Vec::new(),
            timestamp_ns: 0.0,
            camera_fps: 0.0,
            distributor_timestamps: DistributorTimestamps {
                cycle_start_ns: 0,
                slot_write_done_ns: 0,
                barrier_release_ns: 0,
                barrier_return_ns: 0,
            },
        }));
        let slot_for_agg = slot.clone();

        let mut cmd_senders_guard = self.cmd_senders.lock().unwrap();

        // ── Distributor command channel ──
        let (dist_cmd_tx, dist_cmd_rx) = mpsc::channel();
        cmd_senders_guard.push(dist_cmd_tx);

        // ── Spawn distributor thread ──
        let distributor = Distributor::new(
            barrier.clone(),
            slot,
            dist_cmd_rx,
            self.frame_slots.clone(),
            None, // video_timestamps_slot — None for camera source
            None, // last_consumed_frame — None for camera source
            None, // video_rx — None for camera source
            self.shutdown_flag.clone(),
        );
        let dist_stats = self.distributor_stats.clone();
        let dist_handle = std::thread::Builder::new()
            .name("freemocap-distributor".into())
            .spawn(move || {
                let stats = distributor::run_distributor(distributor);
                if let Ok(mut guard) = dist_stats.lock() {
                    *guard = Some(stats);
                }
            })
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!(
                    "Failed to spawn distributor thread: {e}"
                ))
            })?;

        let mut handles: Vec<JoinHandle<()>> = vec![dist_handle];

        // ── Per-camera output channels ──
        let mut camera_rxs: Vec<(String, mpsc::Receiver<CameraNodeOutput>)> = Vec::new();

        // ── Spawn camera node threads ──
        for cam_id in &self.camera_ids {
            let (cam_cmd_tx, cam_cmd_rx) = mpsc::channel();
            cmd_senders_guard.push(cam_cmd_tx);

            let (cam_out_tx, cam_out_rx) = mpsc::channel();
            camera_rxs.push((cam_id.clone(), cam_out_rx));

            let detector = CharucoTracker::new(
                self.config.charuco_config.squares_x,
                self.config.charuco_config.squares_y,
                self.config.charuco_config.square_length_mm,
                self.config.charuco_config.marker_length_ratio,
                self.config.charuco_config.dictionary_enum,
            )
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!(
                    "Failed to create CharucoTracker for camera {cam_id}: {e}"
                ))
            })?;

            let cam_node = CameraNode {
                camera_id: cam_id.clone(),
                cmd_rx: cam_cmd_rx,
                output_tx: cam_out_tx,
                barrier: barrier.clone(),
                slot: slot_for_agg.clone(),
                shutdown_flag: self.shutdown_flag.clone(),
            };

            let cam_stats = self.camera_stats.clone();
            let cam_handle = std::thread::Builder::new()
                .name(format!("freemocap-camera-{cam_id}"))
                .spawn(move || {
                    let stats = camera_node::run_camera_node(cam_node, detector);
                    if let Ok(mut guard) = cam_stats.lock() {
                        guard.push(stats);
                    }
                })
                .map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "Failed to spawn camera node thread for {cam_id}: {e}"
                    ))
                })?;

            handles.push(cam_handle);
        }

        drop(cmd_senders_guard);

        // ── Spawn aggregator thread ──
        let (agg_cmd_tx, agg_cmd_rx) = mpsc::channel();
        {
            let mut guard = self.cmd_senders.lock().unwrap();
            guard.push(agg_cmd_tx);
        }

        let has_calibration = self.calibration.is_some();
        let agg = Aggregator {
            camera_rxs,
            cmd_rx: agg_cmd_rx,
            output_slot: self.output_slot.clone(),
            result_ready: Arc::new(AtomicBool::new(false)),
            shutdown_flag: self.shutdown_flag.clone(),
            distributor_slot: slot_for_agg,
            calibration: self.calibration.clone(),
            triangulation_enabled: has_calibration,
            rejection_config: Default::default(),
            max_reprojection_error_px: 60.0,
        };

        let agg_stats = self.aggregator_stats.clone();
        let agg_handle = std::thread::Builder::new()
            .name("freemocap-aggregator".into())
            .spawn(move || {
                let stats = aggregator::run_aggregator(agg);
                if let Ok(mut guard) = agg_stats.lock() {
                    *guard = Some(stats);
                }
            })
            .map_err(|e| {
                pyo3::exceptions::PyRuntimeError::new_err(format!(
                    "Failed to spawn aggregator thread: {e}"
                ))
            })?;

        handles.push(agg_handle);

        *handles_guard = Some(handles);
        Ok(())
    }

    fn shutdown(&mut self) -> PyResult<()> {
        self.shutdown_flag.store(true, Ordering::SeqCst);

        if let Ok(guard) = self.cmd_senders.lock() {
            for sender in guard.iter() {
                let _ = sender.send(PipelineCommand::Shutdown);
            }
        }

        self.barrier.break_barrier();

        // Join all threads — each writes its stats into the shared slots
        // before exiting, so stats are available after join returns.
        if let Ok(mut guard) = self.handles.lock() {
            if let Some(handles) = guard.take() {
                for handle in handles {
                    let _ = handle.join();
                }
            }
        }

        // Collect stats from shared slots (threads have exited by now)
        let distributor_stats = self
            .distributor_stats
            .lock()
            .ok()
            .and_then(|g| g.clone())
            .unwrap_or_default();
        let camera_stats: Vec<CameraNodeStats> = self
            .camera_stats
            .lock()
            .ok()
            .map(|g| g.clone())
            .unwrap_or_default();
        let aggregator_stats = self
            .aggregator_stats
            .lock()
            .ok()
            .and_then(|g| g.clone())
            .unwrap_or_default();
        let wall_time_secs = self
            .started_at
            .lock()
            .ok()
            .and_then(|g| g.map(|t| t.elapsed().as_secs_f64()))
            .unwrap_or(0.0);

        let n_frames = aggregator_stats.total_ns.len();
        let pipeline_stats = PipelineStats {
            n_frames,
            wall_time_secs,
            dispatcher: None, // No video dispatcher in camera path
            distributor: distributor_stats,
            cameras: camera_stats,
            aggregator: aggregator_stats,
        };
        print_pipeline_stats(&pipeline_stats);

        Ok(())
    }

    fn update_config(&self, config_json: &str) -> PyResult<()> {
        let config: PipelineConfig = serde_json::from_str(config_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Invalid pipeline config JSON: {e}"
            ))
        })?;

        if let Ok(guard) = self.cmd_senders.lock() {
            for sender in guard.iter() {
                sender
                    .send(PipelineCommand::UpdateConfig(config.clone()))
                    .map_err(|e| {
                        pyo3::exceptions::PyRuntimeError::new_err(format!(
                            "Failed to send config update: {e}"
                        ))
                    })?;
            }
        }

        Ok(())
    }

    fn get_latest_output(&self, py: Python<'_>) -> PyResult<Option<Py<PyDict>>> {
        let guard = self.output_slot.lock().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Lock poisoned: {e}"))
        })?;

        match guard.as_ref() {
            Some(output) => {
                let dict = PyDict::new(py);
                dict.set_item("frame_number", output.frame_number)?;
                dict.set_item("camera_ids", &self.camera_ids)?;
                dict.set_item(
                    "frontend_payload",
                    PyBytes::new(py, &output.frontend_payload_bytes),
                )?;
                dict.set_item("timestamp_ns", output.timestamp_ns)?;
                dict.set_item("camera_fps", output.camera_fps)?;

                // Triangulated 3D keypoints
                let raw_dict = PyDict::new(py);
                for (name, xyz) in &output.keypoints_raw {
                    raw_dict.set_item(name, [xyz[0], xyz[1], xyz[2]])?;
                }
                dict.set_item("keypoints_raw", raw_dict)?;

                let filtered_dict = PyDict::new(py);
                for (name, xyz) in &output.keypoints_filtered {
                    filtered_dict.set_item(name, [xyz[0], xyz[1], xyz[2]])?;
                }
                dict.set_item("keypoints_filtered", filtered_dict)?;

                // Per-camera charuco observations (for overlay visualization)
                let cam_obs = PyDict::new(py);
                for cam_output in &output.camera_outputs {
                    if let Some(ref obs) = cam_output.charuco_observation {
                        let obs_dict = PyDict::new(py);
                        obs_dict.set_item(
                            "corner_ids",
                            obs.detected_charuco_corner_ids.clone(),
                        )?;
                        obs_dict.set_item(
                            "corner_points",
                            obs.detected_charuco_corners_image_coordinates
                                .iter()
                                .map(|pt| [pt[0], pt[1]])
                                .collect::<Vec<_>>(),
                        )?;
                        cam_obs.set_item(&cam_output.camera_id, obs_dict)?;
                    }
                }
                dict.set_item("camera_observations", cam_obs)?;

                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    fn camera_ids(&self) -> Vec<String> {
        self.camera_ids.clone()
    }

    fn alive(&self) -> bool {
        !self.shutdown_flag.load(Ordering::Relaxed)
    }
}

impl Drop for PyO3Pipeline {
    fn drop(&mut self) {
        if !self.shutdown_flag.load(Ordering::Relaxed) {
            self.shutdown_flag.store(true, Ordering::SeqCst);
            if let Ok(guard) = self.cmd_senders.lock() {
                for sender in guard.iter() {
                    let _ = sender.send(PipelineCommand::Shutdown);
                }
            }
            self.barrier.break_barrier();
            if let Ok(mut guard) = self.handles.lock() {
                if let Some(handles) = guard.take() {
                    for handle in handles {
                        let _ = handle.join();
                    }
                }
            }
        }
    }
}
