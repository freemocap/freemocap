//! Orchestrated test suite — runs each test module sequentially.
//!
//! Usage:
//!   cargo run --release -- test all [--data-dir PATH] [--calibration PATH] [--max-frames N]
//!
//! Test order: detect → video → calibration → charuco → filtering → pipeline (E2E).
//! Earlier tests validate prerequisites for later ones.

use super::info_block;
use crate::cli::{
    self, AllArgs, CalibrationArgs, CharucoArgs, DetectArgs, FilteringArgs,
    PipelineArgs, VideoArgs,
};

pub fn run(args: &AllArgs) -> anyhow::Result<()> {
    let data_dir = cli::resolve_data_dir(&args.data_dir);
    let calib_path = cli::resolve_calibration_path(&args.calibration, &data_dir);
    let max_frames = args.max_frames;

    info_block(&[
        "",
        &format!(
            "╔══════════════════════════════════════════════════════════════╗\n║           FREEMOCAP RUST — FULL TEST SUITE                   ║\n╠══════════════════════════════════════════════════════════════╣\n║  Data directory:  {:<45}║\n║  Calibration:     {:<45}║\n║  Max frames:      {:<45}║\n╚══════════════════════════════════════════════════════════════╝",
            data_dir, calib_path, max_frames,
        ),
        "",
    ]);

    let mut passed: Vec<String> = Vec::new();
    let mut failed: Vec<String> = Vec::new();
    let suite_start = std::time::Instant::now();

    let detect_args = DetectArgs { data_dir: Some(data_dir.clone()) };
    let video_args = VideoArgs { data_dir: Some(data_dir.clone()), max_frames };
    let calib_args = CalibrationArgs { calibration: calib_path.clone() };
    let charuco_args = CharucoArgs { data_dir: Some(data_dir.clone()), max_frames };
    let filtering_args = FilteringArgs { max_frames: 30 };
    let pipeline_args = PipelineArgs {
        data_dir: Some(data_dir.clone()),
        calibration: Some(calib_path.clone()),
        max_frames,
    };

    // ── 1. Detect (always first — validates environment) ──────────────────
    run_test("detect", &mut passed, &mut failed, || {
        super::detect_tests::run(&detect_args)
    });

    // Only continue if detect passed
    if !failed.is_empty() {
        tracing::error!("Environment check failed — cannot continue.\n");
        print_summary(&passed, &failed, &[], suite_start.elapsed().as_secs_f64());
        anyhow::bail!("Test suite aborted: environment check failed");
    }

    // ── 2. Video reader/dispatcher ────────────────────────────────────────
    run_test("video", &mut passed, &mut failed, || {
        super::video_tests::run(&video_args)
    });

    // ── 3. Calibration ───────────────────────────────────────────────────
    run_test("calibration", &mut passed, &mut failed, || {
        super::calibration_tests::run(&calib_args)
    });

    // ── 4. Charuco detection ──────────────────────────────────────────────
    run_test("charuco", &mut passed, &mut failed, || {
        super::charuco_tests::run(&charuco_args)
    });

    // ── 5. Filtering ──────────────────────────────────────────────────────
    run_test("filtering", &mut passed, &mut failed, || {
        super::filtering_tests::run(&filtering_args)
    });

    // ── 6. E2E Pipeline (the heavy one — runs last) ───────────────────────
    run_test("pipeline (E2E)", &mut passed, &mut failed, || {
        super::pipeline_tests::run(&pipeline_args)
    });

    // ── Summary ──────────────────────────────────────────────────────────
    let elapsed = suite_start.elapsed().as_secs_f64();
    print_summary(&passed, &failed, &[], elapsed);

    if !failed.is_empty() {
        eprintln!(
            "{} test(s) failed: {}",
            failed.len(),
            failed.join(", ")
        );
        std::process::exit(1);
    }

    Ok(())
}

fn run_test(
    name: &str,
    passed: &mut Vec<String>,
    failed: &mut Vec<String>,
    test_fn: impl FnOnce() -> anyhow::Result<()>,
) {
    let start = std::time::Instant::now();
    tracing::info!("  ── {name} ──");
    match test_fn() {
        Ok(()) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::info!("  ✓ PASS: {name} ({elapsed:.1}s)\n");
            passed.push(name.to_string());
        }
        Err(e) => {
            let elapsed = start.elapsed().as_secs_f64();
            tracing::error!("  ✗ FAIL: {name} ({elapsed:.1}s) — {e}\n");
            failed.push(name.to_string());
        }
    }
}

fn print_summary(
    passed: &[String],
    failed: &[String],
    skipped: &[String],
    elapsed: f64,
) {
    let mut lines: Vec<String> = Vec::new();
    lines.push(String::new());
    lines.push("╔══════════════════════════════════════════════════════════════════╗".to_string());
    lines.push("║           FREEMOCAP RUST — TEST SUITE RESULTS                    ║".to_string());
    lines.push("╠══════════════════════════════════════════════════════════════════╣".to_string());
    lines.push(format!(
        "║  Duration:  {:.0}s  ({:.1} min)                                      ║",
        elapsed, elapsed / 60.0,
    ));
    lines.push(format!("║  ✓  {:>3} passed                                                       ║", passed.len()));
    lines.push(format!("║  ✗  {:>3} failed                                                       ║", failed.len()));
    if !skipped.is_empty() {
        lines.push(format!("║  ⏭  {:>3} skipped                                                      ║", skipped.len()));
    }
    lines.push("╠══════════════════════════════════════════════════════════════════╣".to_string());

    if !passed.is_empty() {
        lines.push("║                                                                    ║".to_string());
        for name in passed {
            lines.push(format!("║    ✓  {name:<56}║"));
        }
    }

    if !failed.is_empty() {
        lines.push("║                                                                    ║".to_string());
        lines.push("║  FAILURES:                                                         ║".to_string());
        for name in failed {
            lines.push(format!("║    ✗  {name:<56}║"));
        }
    }

    if !skipped.is_empty() {
        lines.push("║                                                                    ║".to_string());
        lines.push("║  SKIPPED:                                                          ║".to_string());
        for name in skipped {
            lines.push(format!("║    ⏭  {name:<56}║"));
        }
    }
    lines.push("╚══════════════════════════════════════════════════════════════════╝".to_string());
    lines.push(String::new());

    tracing::info!("\n{}", lines.join("\n"));
}
