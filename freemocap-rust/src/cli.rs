//! CLI argument types — parsed by clap derive.
//!
//! Pattern: each test module gets its own args struct. The struct IS the config —
//! no separate config types, no stringly-typed args. All paths have reasonable
//! defaults pointing at the standard test data directory.

use clap::{Parser, Subcommand};

/// FreeMoCap Rust — multi-camera mocap pipeline and test harness.
#[derive(Parser)]
#[command(name = "freemocap-rust", version)]
pub struct Cli {
    /// Start the web server on 0.0.0.0:53118
    #[arg(long, global = true)]
    pub serve: bool,

    #[command(subcommand)]
    pub command: Option<Commands>,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Start the HTTP + WebSocket server
    Serve,
    /// Run pipeline test modules
    Test {
        #[command(subcommand)]
        module: TestModule,
    },
}

#[derive(Subcommand)]
pub enum TestModule {
    /// Run the full test suite (detect → calibration → video → charuco → pipeline → filtering)
    All(AllArgs),
    /// Check test data, OpenCV, and build environment
    Detect(DetectArgs),
    /// E2E pipeline test — VideoGroup → distributor → camera nodes → aggregator → triangulated 3D
    Pipeline(PipelineArgs),
    /// Calibration loading + DLT triangulation unit tests
    Calibration(CalibrationArgs),
    /// Charuco detection performance test
    Charuco(CharucoArgs),
    /// Video reader/dispatcher tests
    Video(VideoArgs),
    /// One Euro filter + velocity gate tests
    Filtering(FilteringArgs),
}

// ── Argument structs ──────────────────────────────────────────────────────────

/// Arguments for the full test suite.
#[derive(clap::Args, Clone)]
pub struct AllArgs {
    /// Test data directory (contains synchronized_videos/ and calibration TOML)
    #[arg(long = "data-dir", value_name = "PATH")]
    pub data_dir: Option<String>,

    /// Calibration TOML path (default: <data-dir>/freemocap_test_data_camera_calibration.toml)
    #[arg(long = "calibration", value_name = "PATH")]
    pub calibration: Option<String>,

    /// Max frames to process in pipeline E2E test (default: 30)
    #[arg(long = "max-frames", default_value = "30")]
    pub max_frames: usize,
}

/// Arguments for environment detection.
#[derive(clap::Args, Clone)]
pub struct DetectArgs {
    /// Test data directory to check
    #[arg(long = "data-dir", value_name = "PATH")]
    pub data_dir: Option<String>,
}

/// Arguments for E2E pipeline test.
#[derive(clap::Args, Clone)]
pub struct PipelineArgs {
    /// Test data directory
    #[arg(long = "data-dir", value_name = "PATH")]
    pub data_dir: Option<String>,

    /// Calibration TOML path
    #[arg(long = "calibration", value_name = "PATH")]
    pub calibration: Option<String>,

    /// Max frames to process (default: 30)
    #[arg(long = "max-frames", default_value = "30")]
    pub max_frames: usize,
}

/// Arguments for calibration + triangulation tests.
#[derive(clap::Args, Clone)]
pub struct CalibrationArgs {
    /// Calibration TOML path (required)
    #[arg(long = "calibration", value_name = "PATH")]
    pub calibration: String,
}

/// Arguments for charuco detection test.
#[derive(clap::Args, Clone)]
pub struct CharucoArgs {
    /// Test data directory
    #[arg(long = "data-dir", value_name = "PATH")]
    pub data_dir: Option<String>,

    /// Max frames to test (default: 10)
    #[arg(long = "max-frames", default_value = "10")]
    pub max_frames: usize,
}

/// Arguments for video reader/dispatcher tests.
#[derive(clap::Args, Clone)]
pub struct VideoArgs {
    /// Test data directory
    #[arg(long = "data-dir", value_name = "PATH")]
    pub data_dir: Option<String>,

    /// Max frames to test (default: 10)
    #[arg(long = "max-frames", default_value = "10")]
    pub max_frames: usize,
}

/// Arguments for filtering tests.
#[derive(clap::Args, Clone)]
pub struct FilteringArgs {
    /// Max frames to test (default: 30)
    #[arg(long = "max-frames", default_value = "30")]
    pub max_frames: usize,
}

// ── Path resolution helpers ───────────────────────────────────────────────────

/// Default test data directory (Windows path — the canonical location).
pub const DEFAULT_DATA_DIR: &str =
    r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data";

/// Default calibration TOML filename within the data directory.
pub const DEFAULT_CALIBRATION_FILENAME: &str =
    "freemocap_test_data_camera_calibration.toml";

/// Resolve data directory: explicit arg → env var → default.
pub fn resolve_data_dir(explicit: &Option<String>) -> String {
    explicit
        .clone()
        .or_else(|| std::env::var("FREEMOCAP_TEST_DATA_DIR").ok())
        .unwrap_or_else(|| DEFAULT_DATA_DIR.to_string())
}

/// Resolve calibration path: explicit arg → <data_dir>/<default filename>.
pub fn resolve_calibration_path(explicit: &Option<String>, data_dir: &str) -> String {
    explicit
        .clone()
        .unwrap_or_else(|| format!("{}/{}", data_dir, DEFAULT_CALIBRATION_FILENAME))
}

/// Resolve synchronized video directory: <data_dir>/synchronized_videos.
pub fn resolve_video_dir(data_dir: &str) -> String {
    format!("{}/synchronized_videos", data_dir)
}
