//! PyO3 bridge module — exposes the pipeline engine to Python.
//!
//! Primary entry point: `_freemocap_rust.RealtimeEngine`
//!   engine = _freemocap_rust.RealtimeEngine()
//!   group_id = engine.create_or_update_camera_group(configs_dict)
//!   pipeline_id = engine.create_pipeline(group_id, config_json, camera_ids)
//!   payloads = engine.get_latest_frontend_payloads(if_newer_than=-1)
//!   engine.shutdown()
//!
//! Single-pipeline direct construction (used by tests and standalone scripts):
//!   pipeline = _freemocap_rust.PyO3Pipeline(manager, group_id, config_json, camera_ids)

mod py_pipeline;
mod py_realtime_engine;
mod types;

use pyo3::prelude::*;

#[pymodule]
fn _freemocap_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize logging (idempotent — skellycam may have already called this).
    // Uses skellycam's SkellyFormat for consistent pipe-delimited terminal output.
    skellycam::init_logging(crate::DEFAULT_LOG_LEVEL);

    m.add_class::<py_pipeline::PyO3Pipeline>()?;
    m.add_class::<py_realtime_engine::PyO3RealtimeEngine>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__doc__", "FreeMoCap Rust pipeline engine")?;

    Ok(())
}
