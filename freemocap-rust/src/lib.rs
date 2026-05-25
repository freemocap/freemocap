pub mod api;
pub mod pipeline;
pub mod pipeline_manager;
pub mod triangulation;
pub mod filtering;
pub mod pyo3_bridge;

/// Default log level for the entire process.
/// `RUST_LOG` env var overrides this if set.
pub const DEFAULT_LOG_LEVEL: &str = "freemocap=debug,skellycam=debug,info";

/// Initialize the global tracing subscriber.
///
/// Delegates to skellycam's subscriber setup which includes `SkellyFormat`
/// for consistent pipe-delimited terminal output. Idempotent — subsequent
/// calls are no-ops.
pub fn init_logging(log_level: &str) {
    skellycam::init_logging(log_level);
}
