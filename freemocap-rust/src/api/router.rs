//! Axum router and application setup.

use std::sync::Arc;

use axum::{Router, routing::{delete, get, post}};
use tower_http::cors::CorsLayer;

use super::routes;
use super::state::AppState;

/// Build the Axum router with all API routes.
pub fn build_router(state: Arc<AppState>) -> Router {
    Router::new()
        // ── Pipeline endpoints ──
        .route("/freemocap/pipeline/create", post(routes::create_pipeline))
        .route("/freemocap/pipeline/list", get(routes::list_pipelines))
        .route(
            "/freemocap/pipeline/{pipeline_id}",
            delete(routes::remove_pipeline),
        )
        .route(
            "/freemocap/pipeline/{pipeline_id}/config",
            post(routes::update_pipeline_config),
        )
        // ── Health ──
        .route("/health", get(|| async { "OK" }))
        // ── Infrastructure ──
        .layer(CorsLayer::permissive())
        .with_state(state)
}
