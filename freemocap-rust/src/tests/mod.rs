pub mod all_tests;
pub mod calibration_tests;
pub mod charuco_tests;
pub mod detect_tests;
pub mod filtering_tests;
pub mod pipeline_tests;
pub mod video_tests;

/// Emit multiple lines as a single `tracing::info!` event.
///
/// Each element is one line. Empty strings produce blank lines.
/// The block is prefixed with `\n` so it is visually separated
/// from the preceding log line.
pub(crate) fn info_block(lines: &[&str]) {
    tracing::info!("\n{}", lines.join("\n"));
}
