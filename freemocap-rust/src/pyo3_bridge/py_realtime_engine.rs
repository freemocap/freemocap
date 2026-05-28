//! PyO3RealtimeEngine — bundles camera management (delegated to skellycam's
//! PyO3CameraGroupManager) with pipeline management (delegated to freemocap's
//! PipelineManager). Follows the same pattern as the Python RealtimeEngine:
//!
//!   Python RealtimeEngine:
//!     ├── CameraGroupManager (skellycam)          ← camera CRUD
//!     └── RealtimePipelineManager (freemocap)     ← pipeline CRUD
//!
//!   Rust PyO3RealtimeEngine:
//!     ├── PyO3CameraGroupManager (skellycam)      ← camera CRUD
//!     └── PipelineManager (freemocap)             ← pipeline CRUD
//!
//! Python sees:
//!   engine = _freemocap_rust.RealtimeEngine()
//!   group_id = engine.create_or_update_camera_group(configs_dict)
//!   pipeline_id = engine.create_pipeline(group_id, config_json, cam_ids)
//!   payloads = engine.get_latest_frontend_payloads(if_newer_than=-1)
//!   engine.shutdown()

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};

use crate::pipeline::config::PipelineConfig;
use crate::pipeline::types::AggregatorOutput;
use crate::pipeline_manager::PipelineManager;
use crate::triangulation::calibration_loader;
use crate::triangulation::charuco::CameraModel;
use skellycam::pyo3_bridge::py_camera_group_manager::PyO3CameraGroupManager;

// ── PyO3 class ───────────────────────────────────────────────────────────────

#[pyclass(name = "RealtimeEngine")]
pub struct PyO3RealtimeEngine {
    camera_manager: PyO3CameraGroupManager,
    pipeline_manager: PipelineManager,
}

#[pymethods]
impl PyO3RealtimeEngine {
    #[new]
    fn new() -> Self {
        Self {
            camera_manager: PyO3CameraGroupManager::default(),
            pipeline_manager: PipelineManager::new(),
        }
    }

    // ── Camera group (delegates to PyO3CameraGroupManager) ──────────────────

    fn create_or_update_camera_group(
        &mut self,
        configs: &Bound<'_, PyDict>,
    ) -> PyResult<String> {
        self.camera_manager.create_or_update_group(configs)
    }

    fn group_count(&self) -> usize {
        self.camera_manager.group_count()
    }

    fn list_groups(&self) -> Vec<String> {
        self.camera_manager.list_groups()
    }

    // ── Pipeline CRUD (delegates to PipelineManager) ────────────────────────

    #[pyo3(signature = (group_id, config_json, camera_ids, calibration_toml_path=None))]
    fn create_pipeline(
        &mut self,
        group_id: &str,
        config_json: &str,
        camera_ids: Vec<String>,
        calibration_toml_path: Option<String>,
    ) -> PyResult<String> {
        let config: PipelineConfig = serde_json::from_str(config_json).map_err(|e| {
            PyValueError::new_err(format!("Invalid pipeline config JSON: {e}"))
        })?;

        let frame_slots =
            self.camera_manager
                .get_frame_slots(group_id)
                .ok_or_else(|| {
                    PyValueError::new_err(format!("CameraGroup '{}' not found", group_id))
                })?;

        let calibration: Option<std::collections::HashMap<String, CameraModel>> =
            match &calibration_toml_path {
                Some(path) => {
                    let models = calibration_loader::load_calibration(
                        &std::path::Path::new(path),
                    )
                    .map_err(|e| {
                        PyValueError::new_err(format!(
                            "Failed to load calibration from '{}': {e}",
                            path
                        ))
                    })?;
                    Some(models)
                }
                None => None,
            };

        self.pipeline_manager
            .create_pipeline(frame_slots, config, group_id, camera_ids, calibration)
            .map_err(|e| PyRuntimeError::new_err(format!("Pipeline creation failed: {e}")))
    }

    fn list_pipelines(&self) -> Vec<String> {
        self.pipeline_manager.list()
    }

    fn pipeline_count(&self) -> usize {
        self.pipeline_manager.count()
    }

    fn shutdown_pipeline(&mut self, pipeline_id: &str) -> bool {
        self.pipeline_manager.shutdown_pipeline(pipeline_id)
    }

    fn update_pipeline_config(&mut self, pipeline_id: &str, config_json: &str) -> PyResult<()> {
        let config: PipelineConfig = serde_json::from_str(config_json).map_err(|e| {
            PyValueError::new_err(format!("Invalid config JSON: {e}"))
        })?;
        self.pipeline_manager
            .update_config(pipeline_id, config)
            .map_err(|e| PyRuntimeError::new_err(format!("Config update failed: {e}")))
    }

    fn pipeline_camera_ids(&self, pipeline_id: &str) -> PyResult<Vec<String>> {
        self.pipeline_manager
            .camera_ids(pipeline_id)
            .ok_or_else(|| PyValueError::new_err(format!("Pipeline '{}' not found", pipeline_id)))
    }

    fn pipeline_alive(&self, pipeline_id: &str) -> bool {
        self.pipeline_manager.is_alive(pipeline_id)
    }

    // ── Output polling (delegates to PipelineManager) ───────────────────────

    fn get_pipeline_output(
        &self,
        py: Python<'_>,
        pipeline_id: &str,
        if_newer_than: i64,
    ) -> PyResult<Option<Py<PyDict>>> {
        match self.pipeline_manager.get_output(pipeline_id, if_newer_than) {
            Some(output) => {
                let group_id = self
                    .pipeline_manager
                    .group_id(pipeline_id)
                    .unwrap_or(pipeline_id);
                let dict = build_output_dict(py, &output, pipeline_id, group_id)?;
                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    fn wait_for_any_result_ready(&self, timeout_secs: f64) -> bool {
        self.pipeline_manager.wait_for_any_result_ready(timeout_secs)
    }

    fn get_latest_frontend_payloads(
        &self,
        py: Python<'_>,
        if_newer_than: i64,
    ) -> PyResult<Vec<Py<PyDict>>> {
        let results: Vec<Py<PyDict>> = self
            .pipeline_manager
            .get_all_outputs(if_newer_than)
            .into_iter()
            .map(|(pid, output)| {
                let gid = self.pipeline_manager.group_id(&pid).unwrap_or(&pid);
                build_output_dict(py, &output, &pid, gid)
            })
            .collect::<Result<_, _>>()?;
        Ok(results)
    }

    // ── Recording (delegates to PyO3CameraGroupManager) ────────────────────

    #[pyo3(signature = (output_dir, label=None))]
    fn start_recording_all(&self, output_dir: &str, label: Option<&str>) -> PyResult<()> {
        self.camera_manager.start_recording(output_dir, label)
    }

    fn stop_recording_all(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        self.camera_manager.stop_recording(py)
    }

    // ── Pause (delegates to PyO3CameraGroupManager) ────────────────────────

    fn pause(&self) {
        self.camera_manager.pause()
    }

    fn unpause(&self) {
        self.camera_manager.unpause()
    }

    fn pause_unpause_all(&self) {
        self.camera_manager.pause_unpause_all()
    }

    // ── Shutdown ──────────────────────────────────────────────────────────

    fn shutdown(&mut self) -> PyResult<()> {
        self.pipeline_manager.shutdown_all();
        self.camera_manager.close_all_groups();
        tracing::info!("[RealtimeEngine] shutdown complete");
        Ok(())
    }

    fn alive(&self) -> bool {
        self.pipeline_manager.list().iter().any(|pid| self.pipeline_manager.is_alive(pid))
    }

    fn __repr__(&self) -> String {
        format!(
            "RealtimeEngine(camera_groups={}, pipelines={})",
            self.camera_manager.group_count(),
            self.pipeline_manager.count(),
        )
    }
}

impl Drop for PyO3RealtimeEngine {
    fn drop(&mut self) {
        self.pipeline_manager.shutdown_all();
        self.camera_manager.close_all_groups();
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

fn build_output_dict(
    py: Python<'_>,
    output: &AggregatorOutput,
    pipeline_id: &str,
    group_id: &str,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("frame_number", output.frame_number)?;
    dict.set_item("pipeline_id", pipeline_id)?;
    dict.set_item("camera_group_id", group_id)?;
    dict.set_item("images_bytearray", PyBytes::new(py, &output.frontend_payload_bytes))?;
    dict.set_item("multiframe_timestamp", output.timestamp_ns)?;

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

    let cam_obs = PyDict::new(py);
    for cam_output in &output.camera_outputs {
        if let Some(ref obs) = cam_output.charuco_observation {
            let obs_dict = PyDict::new(py);
            obs_dict.set_item("corner_ids", obs.detected_charuco_corner_ids.clone())?;
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

    Ok(dict.into())
}