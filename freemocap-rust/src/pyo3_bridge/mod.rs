//! PyO3 bridge module — exposes the pipeline engine to Python.
//!
//! Python imports `_freemocap_rust.PyPipeline` and controls lifecycle:
//!   pipeline = _freemocap_rust.PyPipeline(camera_group_manager, group_id, config_json, camera_ids)
//!   pipeline.start()
//!   output = pipeline.get_latest_output()
//!   pipeline.shutdown()

mod py_pipeline;
mod types;

use pyo3::prelude::*;

#[pymodule]
fn _freemocap_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Initialize logging (idempotent — skellycam may have already called this).
    // Uses skellycam's SkellyFormat for consistent pipe-delimited terminal output.
    skellycam::init_logging(crate::DEFAULT_LOG_LEVEL);

    m.add_class::<py_pipeline::PyPipeline>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__doc__", "FreeMoCap Rust pipeline engine")?;

    Ok(())
}
