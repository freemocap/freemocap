//! Application state shared across all HTTP handlers.
//!
//! Wraps both managers in `Arc<tokio::sync::Mutex<...>>` so they can be
//! cloned cheaply into every Axum handler.

use std::sync::atomic::AtomicBool;
use std::sync::Arc;

use skellycam::camera_group_manager::CameraGroupManager;

use crate::pipeline_manager::PipelineManager;

pub struct AppState {
    pub camera_manager: Arc<tokio::sync::Mutex<CameraGroupManager>>,
    pub pipeline_manager: Arc<tokio::sync::Mutex<PipelineManager>>,
    pub shutdown_flag: Arc<AtomicBool>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            camera_manager: Arc::new(tokio::sync::Mutex::new(CameraGroupManager::new())),
            pipeline_manager: Arc::new(tokio::sync::Mutex::new(PipelineManager::new())),
            shutdown_flag: Arc::new(AtomicBool::new(false)),
        }
    }
}
