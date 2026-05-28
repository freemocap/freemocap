//! One Euro filter + velocity gate tests with synthetic trajectories.
//!
//! Usage:
//!   cargo run --release -- test filtering

use super::info_block;
use crate::cli::FilteringArgs;
use freemocap::filtering::{OneEuroFilter, RealtimePointGate};

pub fn run(args: &FilteringArgs) -> anyhow::Result<()> {
    let max_frames = args.max_frames;

    info_block(&[
        "══════════════════════════════════════════════════",
        &format!("  FILTERING TESTS\n  Frames: {max_frames}"),
        "══════════════════════════════════════════════════",
        "",
    ]);

    // ── Test 1: One Euro filter smooths noise ─────────────────────────────
    tracing::info!("  ── One Euro filter ──");
    let mut euro = OneEuroFilter::new(1.0, 0.01, 1.0);

    // Generate a smooth sine trajectory with added noise
    let clean: Vec<[f64; 3]> = (0..max_frames)
        .map(|i| {
            let t = i as f64 * 0.033; // 30 fps
            [t * 100.0, (t * 2.0).sin() * 200.0, (t * 3.0).cos() * 150.0]
        })
        .collect();

    let noisy: Vec<[f64; 3]> = clean
        .iter()
        .map(|p| {
            // Add Gaussian noise (σ=10mm)
            [p[0] + rand_noise(10.0), p[1] + rand_noise(10.0), p[2] + rand_noise(10.0)]
        })
        .collect();

    let mut filtered: Vec<[f64; 3]> = Vec::with_capacity(max_frames);
    for (i, pt) in noisy.iter().enumerate() {
        let t = i as f64 * 0.033;
        let mut state = std::collections::HashMap::new();
        state.insert("0".to_string(), *pt);
        let filtered_state = euro.filter(t, &state);
        if let Some(fp) = filtered_state.get("0") {
            filtered.push(*fp);
        } else {
            filtered.push(*pt);
        }
    }

    // Compute noise reduction ratio
    let raw_rmse = rmse(&noisy, &clean);
    let filtered_rmse = rmse(&filtered, &clean);
    let reduction = if raw_rmse > 0.0 {
        (1.0 - filtered_rmse / raw_rmse) * 100.0
    } else {
        0.0
    };

    tracing::info!(
        "  Raw RMSE: {:.1}mm  |  Filtered RMSE: {:.1}mm  |  Noise reduction: {:.0}%",
        raw_rmse,
        filtered_rmse,
        reduction,
    );
    assert!(
        filtered_rmse < raw_rmse,
        "One Euro filter should reduce noise (filtered_rmse={:.1} >= raw_rmse={:.1})",
        filtered_rmse, raw_rmse
    );

    // ── Test 2: Velocity gate catches teleport spikes ─────────────────────
    tracing::info!("  ── Velocity gate ──");
    let mut gate = RealtimePointGate::new(3.0, 5); // 3 m/s max, 5 max rejected streak

    let trajectory: Vec<[f64; 3]> = (0..20)
        .map(|i| [i as f64 * 50.0, 0.0, 0.0]) // steady 50mm/frame movement
        .collect();

    let mut accepted = 0usize;
    let mut rejected = 0usize;
    let spike_inserted_at = 10;

    for (i, pt) in trajectory.iter().enumerate() {
        let t = i as f64 * 0.033;
        let mut state = std::collections::HashMap::new();
        // Insert a teleport spike (1000mm away in one frame = 30 m/s)
        let value = if i == spike_inserted_at {
            [1000.0, 500.0, 300.0]
        } else {
            *pt
        };
        state.insert("0".to_string(), value);
        let gated = gate.gate(t, &state);
        if gated.is_empty() {
            rejected += 1;
        } else {
            accepted += 1;
        }
    }

    tracing::info!(
        "  Accepted: {}  |  Rejected: {}  |  (spike at frame {}) {}",
        accepted,
        rejected,
        spike_inserted_at,
        if rejected > 0 { "✓ spike caught" } else { "✗ spike missed" },
    );
    assert!(rejected > 0, "Velocity gate should reject teleport spike (1000mm in one frame)");

    // ── Test 3: Filter stability ──────────────────────────────────────────
    tracing::info!("  ── Filter stability ──");
    let mut stable_euro = OneEuroFilter::new(1.0, 0.01, 1.0);

    let constant: Vec<[f64; 3]> = vec![[100.0, 200.0, 300.0]; max_frames];
    let mut stable_filtered: Vec<[f64; 3]> = Vec::with_capacity(max_frames);

    for (i, pt) in constant.iter().enumerate() {
        let t = i as f64 * 0.033;
        let mut state = std::collections::HashMap::new();
        state.insert("0".to_string(), *pt);
        let filtered_state = stable_euro.filter(t, &state);
        if let Some(fp) = filtered_state.get("0") {
            stable_filtered.push(*fp);
        }
    }

    // Check that filtered output converges to constant input
    let last_third = &stable_filtered[2 * max_frames / 3..];
    let drift = rmse(last_third, &vec![[100.0, 200.0, 300.0]; last_third.len()]);
    tracing::info!("  Final drift from constant: {:.1}mm (should converge to <1mm)", drift);
    assert!(drift < 1.0, "Filter should converge to constant input (drift={:.1}mm)", drift);

    info_block(&[
        "",
        "  ✓ Filtering tests PASSED",
        "",
    ]);

    Ok(())
}

fn rmse(a: &[[f64; 3]], b: &[[f64; 3]]) -> f64 {
    let n = a.len().min(b.len());
    if n == 0 {
        return 0.0;
    }
    let sum_sq: f64 = a[..n]
        .iter()
        .zip(&b[..n])
        .map(|(pa, pb)| {
            let dx = pa[0] - pb[0];
            let dy = pa[1] - pb[1];
            let dz = pa[2] - pb[2];
            dx * dx + dy * dy + dz * dz
        })
        .sum();
    (sum_sq / n as f64).sqrt()
}

fn rand_noise(sigma: f64) -> f64 {
    // Simple pseudo-random noise using xorshift
    static mut SEED: u64 = 123456789;
    unsafe {
        SEED ^= SEED << 13;
        SEED ^= SEED >> 7;
        SEED ^= SEED << 17;
        let u01 = (SEED as f64) / (u64::MAX as f64);
        // Box-Muller-ish approximation: just scale centered uniform
        (u01 - 0.5) * sigma * 2.0
    }
}
