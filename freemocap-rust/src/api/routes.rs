//! Pipeline API routes.
//!
//! Endpoints for creating, querying, updating, and deleting real-time pipelines.

use std::sync::Arc;

use axum::{
    Json,
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};

use super::state::AppState;

#[derive(Debug, Deserialize)]
pub struct CreatePipelineRequest {
    pub group_id: String,
    pub config_json: String,
    pub camera_ids: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct CreatePipelineResponse {
    pub pipeline_id: String,
}

#[derive(Debug, Serialize)]
pub struct PipelineListResponse {
    pub pipeline_ids: Vec<String>,
    pub count: usize,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub detail: String,
}

/// POST /freemocap/pipeline/create
pub async fn create_pipeline(
    State(state): State<Arc<AppState>>,
    Json(req): Json<CreatePipelineRequest>,
) -> impl IntoResponse {
    let mut cam_mgr = state.camera_manager.lock().await;
    let group = match cam_mgr.get_group(&req.group_id) {
        Some(g) => g,
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(serde_json::json!({"detail": format!("CameraGroup '{}' not found", req.group_id)})),
            );
        }
    };

    let frame_slots = group.frame_slots();

    let config = match serde_json::from_str(&req.config_json) {
        Ok(c) => c,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"detail": format!("Invalid config JSON: {e}")})),
            );
        }
    };

    drop(cam_mgr); // release lock before locking pipeline manager

    let mut pipe_mgr = state.pipeline_manager.lock().await;
    let pipeline_id =
        pipe_mgr.create_realtime_pipeline(frame_slots, config, req.camera_ids);

    (StatusCode::CREATED, Json(serde_json::json!(CreatePipelineResponse { pipeline_id })))
}

/// GET /freemocap/pipeline/list
pub async fn list_pipelines(
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    let pipe_mgr = state.pipeline_manager.lock().await;
    let ids = pipe_mgr.list_realtime_pipelines();
    let count = pipe_mgr.realtime_pipeline_count();

    Json(serde_json::json!(PipelineListResponse {
        pipeline_ids: ids,
        count,
    }))
}

/// DELETE /freemocap/pipeline/{pipeline_id}
pub async fn remove_pipeline(
    State(state): State<Arc<AppState>>,
    Path(pipeline_id): Path<String>,
) -> impl IntoResponse {
    let mut pipe_mgr = state.pipeline_manager.lock().await;
    if pipe_mgr.remove_realtime_pipeline(&pipeline_id) {
        (StatusCode::NO_CONTENT, Json(serde_json::json!({})))
    } else {
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"detail": format!("Pipeline '{}' not found", pipeline_id)})),
        )
    }
}

/// POST /freemocap/pipeline/{pipeline_id}/config
pub async fn update_pipeline_config(
    State(state): State<Arc<AppState>>,
    Path(pipeline_id): Path<String>,
    Json(config_json): Json<serde_json::Value>,
) -> impl IntoResponse {
    let config = match serde_json::from_value(config_json) {
        Ok(c) => c,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"detail": format!("Invalid config: {e}")})),
            );
        }
    };

    let mut pipe_mgr = state.pipeline_manager.lock().await;
    if pipe_mgr.update_realtime_pipeline_config(&pipeline_id, config).is_some() {
        (StatusCode::OK, Json(serde_json::json!({})))
    } else {
        (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"detail": format!("Pipeline '{}' not found", pipeline_id)})),
        )
    }
}
