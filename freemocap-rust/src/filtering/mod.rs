//! Signal processing filters for real-time keypoint smoothing.
//!
//! Filters operate on `HashMap<String, [f64; 3]>` — point name → 3D coordinates.
//! All filters are stateful (maintain history across frames).

pub mod one_euro;
pub mod skeleton_filter;
pub mod velocity_gate;

pub use one_euro::OneEuroFilter;
pub use velocity_gate::RealtimePointGate;
