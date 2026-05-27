//! FreeMoCap standalone server binary.
//!
//! Boots a Tokio runtime, builds the Axum router with `AppState`,
//! and serves HTTP endpoints for camera group and pipeline management.
//!
//! The server manages:
//! - **Camera groups** (via skellycam's `CameraGroupManager`) — create, list,
//!   close camera groups. Each group synchronizes N USB cameras.
//! - **Pipelines** (via `PipelineManager`) — create, list, delete real-time
//!   pipelines. Each pipeline attaches to a camera group's `FrameSlots` and
//!   runs the distributor→camera nodes→aggregator thread topology.
//! - **Posthoc pipelines** — deferred. VideoGroup already supports mpsc-channel
//!   based frame delivery for posthoc processing (see `video_reader` module).
//!
//! Usage: `cargo run` (starts server on port 53118 unconditionally).
//! CLI argument parsing (--port, --serve, etc.) deferred to next milestone.

use std::sync::Arc;

fn main() {
    freemocap::init_logging(freemocap::DEFAULT_LOG_LEVEL);

    let state = Arc::new(freemocap::api::AppState::new());
    let router = freemocap::api::build_router(state.clone());

    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()
        .expect("Failed to build Tokio runtime");

    rt.block_on(async {
        let listener = tokio::net::TcpListener::bind("0.0.0.0:53118")
            .await
            .expect("Failed to bind to port 53118");

        tracing::info!("FreeMoCap Rust server listening on http://0.0.0.0:53118");

        axum::serve(listener, router)
            .with_graceful_shutdown(async {
                tokio::signal::ctrl_c().await.ok();
                tracing::info!("Shutdown signal received");
            })
            .await
            .expect("Server error");
    });

    // Cleanup: close all camera groups and pipelines
    state.camera_manager.blocking_lock().close_all_groups();
    state.pipeline_manager.blocking_lock().shutdown_all();
}
