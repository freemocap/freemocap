//! 3D triangulation from multi-camera observations.
//!
//! Takes 2D charuco corner detections from N cameras and computes
//! 3D positions using stereo calibration parameters via DLT.

pub mod calibration_loader;
pub mod charuco;
pub mod dlt;
pub mod outlier_rejection;

#[cfg(test)]
mod integration_test;

