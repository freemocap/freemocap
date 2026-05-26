//! Pipeline timing statistics — per-stage, per-camera, per-thread.
//!
//! Accumulates nanosecond-precision timestamps across all frames and prints
//! a comprehensive statistics block on shutdown. Format matches skellycam's
//! gatherer statistics: per-camera tables with mean/median camera summaries,
//! across-camera spread, and per-metric median/mean/std/CV%/min/max/n.

// ── Stats primitives ─────────────────────────────────────────────────────

struct Stats {
    median: f64,
    mean: f64,
    std: f64,
    cv_pct: f64,
    min: f64,
    max: f64,
    n: usize,
}

fn compute_stats(values: &[f64]) -> Option<Stats> {
    if values.is_empty() {
        return None;
    }
    let n = values.len();
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let mean = values.iter().sum::<f64>() / n as f64;
    let median = sorted[n / 2];
    let min = sorted[0];
    let max = sorted[n - 1];
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n as f64;
    let std = variance.sqrt();
    let cv_pct = if mean.abs() > f64::EPSILON {
        (std / mean) * 100.0
    } else {
        0.0
    };

    Some(Stats {
        median,
        mean,
        std,
        cv_pct,
        min,
        max,
        n,
    })
}

fn auto_unit(values_ns: &[f64]) -> (f64, &'static str) {
    let max = values_ns.iter().cloned().fold(0.0_f64, f64::max);
    if max >= 1_000_000.0 {
        (1_000_000.0, "ms")
    } else if max >= 1_000.0 {
        (1_000.0, "µs")
    } else {
        (1.0, "ns")
    }
}

fn fmt_val(value: f64, div: f64, unit: &str) -> String {
    let v = value / div;
    if v == 0.0 {
        format!("0 {unit}")
    } else if v.abs() >= 10_000.0 {
        format!("{v:.1} {unit}")
    } else if v.abs() >= 1.0 {
        format!("{v:.2} {unit}")
    } else {
        format!("{v:.3} {unit}")
    }
}

fn fmt_pct(value: f64) -> String {
    if value.abs() >= 100.0 {
        format!("{value:.0}%")
    } else if value.abs() >= 10.0 {
        format!("{value:.1}%")
    } else {
        format!("{value:.2}%")
    }
}

// ── Stats accumulators ───────────────────────────────────────────────────

/// Per-camera detection-stage timing samples (one per frame).
#[derive(Debug, Clone, Default)]
pub struct CameraNodeStats {
    pub camera_id: String,
    /// JPEG decode duration (ns).
    pub jpeg_decode_ns: Vec<f64>,
    /// Charuco detection duration (ns).
    pub charuco_detect_ns: Vec<f64>,
    /// Time from dequeue to pre_send (total camera node cycle, ns).
    pub total_ns: Vec<f64>,
    /// Number of charuco corners detected per frame.
    pub corners_detected: Vec<u32>,
}

/// Distributor-stage timing samples (one per frame).
#[derive(Debug, Clone, Default)]
pub struct DistributorStats {
    /// Time spent reading FrameSlots + writing DistributorSlot (ns).
    pub slot_work_ns: Vec<f64>,
    /// Time waiting at BreakableBarrier (ns).
    pub barrier_wait_ns: Vec<f64>,
    /// Full distributor cycle: slot read → slot write → barrier release (ns).
    pub total_ns: Vec<f64>,
}

/// Aggregator-stage timing samples (one per frame).
#[derive(Debug, Clone, Default)]
pub struct AggregatorStats {
    /// Time from collection start to all cameras received (includes recv blocking, ns).
    pub collection_ns: Vec<f64>,
    /// Triangulation computation only (ns).
    pub triangulation_ns: Vec<f64>,
    /// Velocity gate + One Euro filter (ns).
    pub filtering_ns: Vec<f64>,
    /// Output publish time (ns).
    pub output_publish_ns: Vec<f64>,
    /// Full aggregator cycle: collection → triangulation → filter → publish (ns).
    pub total_ns: Vec<f64>,
    /// Number of 3D points triangulated per frame.
    pub points_triangulated: Vec<usize>,
}

/// Video dispatcher timing samples (one per multiframe, optional).
#[derive(Debug, Clone, Default)]
pub struct VideoDispatcherStats {
    /// Video frame read time: read_done - read_start (ns).
    pub read_ns: Vec<f64>,
    /// BGR → JPEG encoding time (ns).
    pub encode_ns: Vec<f64>,
    /// Payload construction time (ns).
    pub payload_build_ns: Vec<f64>,
    /// FrameSlots write time (ns).
    pub slots_write_ns: Vec<f64>,
    /// Full dispatcher cycle: read → encode → build → write (ns).
    pub total_ns: Vec<f64>,
}

/// Complete pipeline statistics across all threads.
#[derive(Debug, Clone, Default)]
pub struct PipelineStats {
    pub n_frames: usize,
    pub wall_time_secs: f64,
    pub dispatcher: Option<VideoDispatcherStats>,
    pub distributor: DistributorStats,
    pub cameras: Vec<CameraNodeStats>,
    pub aggregator: AggregatorStats,
}

// ── Printing ─────────────────────────────────────────────────────────────

struct TableSchema {
    name_w: usize,
    cell_widths: Vec<usize>,
}

impl TableSchema {
    fn print_header(&self, out: &mut String, name_label: &str, headers: &[&str]) {
        out.push_str("  ");
        out.push_str(&format!("{name_label:<w$}", w = self.name_w));
        for (h, w) in headers.iter().zip(&self.cell_widths) {
            out.push_str(" │ ");
            out.push_str(&format!("{h:>cw$}", cw = *w));
        }
        out.push('\n');
    }

    fn print_separator(&self, out: &mut String) {
        out.push_str("  ");
        out.push_str(&"─".repeat(self.name_w));
        for w in &self.cell_widths {
            out.push_str("─┼─");
            out.push_str(&"─".repeat(*w));
        }
        out.push('\n');
    }

    fn print_row(&self, out: &mut String, name: &str, cells: &[String]) {
        out.push_str("  ");
        out.push_str(&format!("{name:<w$}", w = self.name_w));
        for (cell, w) in cells.iter().zip(&self.cell_widths) {
            out.push_str(" │ ");
            out.push_str(&format!("{cell:>cw$}", cw = *w));
        }
        out.push('\n');
    }
}

fn summary_cells(stats: &Stats, div: f64, unit: &str) -> Vec<String> {
    vec![
        fmt_val(stats.median, div, unit),
        fmt_val(stats.mean, div, unit),
        fmt_val(stats.std, div, unit),
        fmt_pct(stats.cv_pct),
        fmt_val(stats.min, div, unit),
        fmt_val(stats.max, div, unit),
        stats.n.to_string(),
    ]
}

fn per_camera_cells(stats: &Stats, div: f64, unit: &str, pct_of_total: Option<f64>) -> Vec<String> {
    vec![
        fmt_val(stats.median, div, unit),
        fmt_val(stats.mean, div, unit),
        fmt_val(stats.std, div, unit),
        fmt_pct(stats.cv_pct),
        pct_of_total.map(fmt_pct).unwrap_or_else(|| "—".to_string()),
        stats.n.to_string(),
    ]
}

/// Print per-camera metric table with mean/median camera summary rows.
fn print_per_camera_table(
    out: &mut String,
    metric_name: &str,
    formula: &str,
    schema: &TableSchema,
    per_camera_values: &[Vec<f64>],
    per_camera_totals: &[Vec<f64>],
    camera_labels: &[String],
) {
    out.push_str(&format!("  > {metric_name}  {formula}\n"));

    let all_values: Vec<f64> = per_camera_values.iter().flat_map(|v| v.iter().copied()).collect();
    if all_values.is_empty() {
        out.push_str("    (no samples)\n\n");
        return;
    }
    let (div, unit) = auto_unit(&all_values);

    schema.print_header(out, "Camera", &["Median", "Mean", "Std", "CV%", "% total", "n"]);
    schema.print_separator(out);

    let mut acc_medians = Vec::new();
    let mut acc_means = Vec::new();
    let mut acc_stds = Vec::new();
    let mut acc_cvs = Vec::new();
    let mut acc_pcts = Vec::new();

    for (i, values) in per_camera_values.iter().enumerate() {
        let label = camera_labels.get(i).cloned().unwrap_or_default();
        let stats = match compute_stats(values) {
            Some(s) => s,
            None => continue,
        };
        let pct_of_total = per_camera_totals.get(i).and_then(|t| compute_stats(t)).map(|ts| {
            if ts.median > 0.0 { (stats.median / ts.median) * 100.0 } else { 0.0 }
        });

        acc_medians.push(stats.median);
        acc_means.push(stats.mean);
        acc_stds.push(stats.std);
        acc_cvs.push(stats.cv_pct);
        if let Some(p) = pct_of_total { acc_pcts.push(p); }

        schema.print_row(out, &label, &per_camera_cells(&stats, div, unit, pct_of_total));
    }

    if acc_medians.len() >= 2 {
        let s_med = compute_stats(&acc_medians);
        let s_mean = compute_stats(&acc_means);
        let s_std = compute_stats(&acc_stds);
        let s_cv = compute_stats(&acc_cvs);
        let s_pct = if acc_pcts.is_empty() { None } else { compute_stats(&acc_pcts) };

        schema.print_separator(out);

        let val_cell = |opt: &Option<Stats>, f: fn(&Stats) -> f64| -> String {
            opt.as_ref().map_or("—".to_string(), |s| fmt_val(f(s), div, unit))
        };
        let pct_cell = |opt: &Option<Stats>, f: fn(&Stats) -> f64| -> String {
            opt.as_ref().map_or("—".to_string(), |s| fmt_pct(f(s)))
        };

        schema.print_row(out, "Mean camera", &[
            val_cell(&s_med, |s| s.mean),
            val_cell(&s_mean, |s| s.mean),
            val_cell(&s_std, |s| s.mean),
            pct_cell(&s_cv, |s| s.mean),
            pct_cell(&s_pct, |s| s.mean),
            "—".to_string(),
        ]);
        schema.print_row(out, "Median camera", &[
            val_cell(&s_med, |s| s.median),
            val_cell(&s_mean, |s| s.median),
            val_cell(&s_std, |s| s.median),
            pct_cell(&s_cv, |s| s.median),
            pct_cell(&s_pct, |s| s.median),
            "—".to_string(),
        ]);

        let spread = acc_medians.iter().cloned().fold(f64::MIN, f64::max)
            - acc_medians.iter().cloned().fold(f64::MAX, f64::min);
        let across_cv = s_med.as_ref().map_or(0.0, |s| s.cv_pct);
        schema.print_separator(out);
        out.push_str(&format!(
            "  Across cameras (of {} per-camera medians):  spread {}  │  CV% {}\n",
            acc_medians.len(),
            fmt_val(spread, div, unit),
            fmt_pct(across_cv),
        ));
    }
    out.push('\n');
}

/// Print per-thread summary table (one row per metric).
fn print_summary_table(
    out: &mut String,
    title: &str,
    metrics: &[(&str, &[f64])],
) {
    out.push_str(&format!("▸ {title} ─"));
    out.push_str(&"─".repeat(80_usize.saturating_sub(title.len() + 3)));
    out.push_str("\n\n");

    let all_values: Vec<f64> = metrics.iter()
        .flat_map(|(_, v)| v.iter().copied())
        .collect();
    if all_values.is_empty() {
        out.push_str("    (no samples)\n\n");
        return;
    }
    let (div, unit) = auto_unit(&all_values);

    let schema = TableSchema {
        name_w: 26,
        cell_widths: vec![10, 10, 10, 6, 10, 10, 4],
    };
    schema.print_header(out, "Metric", &["Median", "Mean", "Std", "CV%", "Min", "Max", "n"]);
    schema.print_separator(out);

    for (name, values) in metrics {
        match compute_stats(values) {
            Some(stats) => {
                schema.print_row(out, name, &summary_cells(&stats, div, unit));
            }
            None => {
                schema.print_row(out, name, &["(no samples)".to_string()]);
            }
        }
    }
    out.push('\n');
}

/// Print the full pipeline statistics block.
pub fn print_pipeline_stats(stats: &PipelineStats) {
    let mut out = String::new();

    out.push('\n');
    out.push_str("═══════════════════════════════════════════════════════════════════════════════\n");
    out.push_str("  PIPELINE STATISTICS\n");
    out.push_str(&format!(
        "  {} cameras, {} multiframes observed, {:.1}s wall time\n",
        stats.cameras.len(),
        stats.n_frames,
        stats.wall_time_secs,
    ));
    out.push_str("  All timestamps in auto-scaled units (ns / µs / ms).\n");
    if stats.cameras.is_empty() {
        out.push_str("  NO CAMERA DATA\n");
    }
    out.push_str("───────────────────────────────────────────────────────────────────────────────\n");
    out.push('\n');

    // ── 1. Throughput ──
    if stats.n_frames > 0 {
        let fps: Vec<f64> = stats.aggregator.total_ns.iter()
            .map(|ns| 1_000_000_000.0 / ns)
            .collect();
        let period_ms: Vec<f64> = stats.aggregator.total_ns.iter()
            .map(|ns| ns / 1_000_000.0)
            .collect();

        // Throughput uses mixed units: FPS (fps) and duration (ms)
        out.push_str("▸ THROUGHPUT ────────────────────────────────────────────────────────────────\n\n");
        let schema = TableSchema {
            name_w: 26,
            cell_widths: vec![10, 10, 10, 6, 10, 10, 4],
        };
        schema.print_header(&mut out, "Metric", &["Median", "Mean", "Std", "CV%", "Min", "Max", "n"]);
        schema.print_separator(&mut out);

        // FPS — no division, unit is "fps"
        if let Some(s) = compute_stats(&fps) {
            let cells = vec![
                format!("{:.2} fps", s.median),
                format!("{:.2} fps", s.mean),
                format!("{:.2} fps", s.std),
                fmt_pct(s.cv_pct),
                format!("{:.2} fps", s.min),
                format!("{:.2} fps", s.max),
                s.n.to_string(),
            ];
            schema.print_row(&mut out, "Pipeline FPS", &cells);
        }
        // Frame duration — always in ms
        if let Some(s) = compute_stats(&period_ms) {
            let cells = vec![
                format!("{:.2} ms", s.median),
                format!("{:.2} ms", s.mean),
                format!("{:.2} ms", s.std),
                fmt_pct(s.cv_pct),
                format!("{:.2} ms", s.min),
                format!("{:.2} ms", s.max),
                s.n.to_string(),
            ];
            schema.print_row(&mut out, "Frame duration", &cells);
        }
        out.push('\n');
    }

    // ── 2. Video dispatcher (if present) ──
    if let Some(ref d) = stats.dispatcher {
        print_summary_table(&mut out, "VIDEO DISPATCHER", &[
            ("Read frames", &d.read_ns),
            ("JPEG encode", &d.encode_ns),
            ("Payload build", &d.payload_build_ns),
            ("Slots write", &d.slots_write_ns),
            ("Total dispatcher", &d.total_ns),
        ]);
    }

    // ── 3. Distributor ──
    print_summary_table(&mut out, "DISTRIBUTOR", &[
        ("Slot poll + write", &stats.distributor.slot_work_ns),
        ("Barrier wait", &stats.distributor.barrier_wait_ns),
        ("Total distributor", &stats.distributor.total_ns),
    ]);

    // ── 4. Per-camera detection ──
    let n_cameras = stats.cameras.len();
    let total_camera_samples: usize = stats.cameras.iter().map(|c| c.jpeg_decode_ns.len()).sum();
    out.push_str(&format!(
        "▸ PER-CAMERA DETECTION  (one sample per camera per multiframe; {} total) ────\n",
        total_camera_samples,
    ));
    out.push_str("  One table per metric. Each table: per-camera rows (ordered by\n");
    out.push_str("  camera_id) + across-cameras summary rows (mean + median camera).\n");
    out.push('\n');

    if n_cameras > 0 {
        let max_label_len = stats.cameras.iter()
            .map(|c| c.camera_id.len())
            .max()
            .unwrap_or(0)
            .max(26);
        let per_camera_schema = TableSchema {
            name_w: max_label_len,
            cell_widths: vec![10, 10, 10, 6, 8, 4],
        };

        let camera_labels: Vec<String> = stats.cameras.iter().map(|c| c.camera_id.clone()).collect();
        let decode: Vec<Vec<f64>> = stats.cameras.iter().map(|c| c.jpeg_decode_ns.clone()).collect();
        let detect: Vec<Vec<f64>> = stats.cameras.iter().map(|c| c.charuco_detect_ns.clone()).collect();
        let totals: Vec<Vec<f64>> = stats.cameras.iter().map(|c| c.total_ns.clone()).collect();

        print_per_camera_table(
            &mut out, "JPEG DECODE", "(post_jpeg_decode_ns − dequeue_ns)",
            &per_camera_schema, &decode, &totals, &camera_labels,
        );
        print_per_camera_table(
            &mut out, "CHARUCO DETECT", "(post_detection_ns − post_jpeg_decode_ns)",
            &per_camera_schema, &detect, &totals, &camera_labels,
        );
        print_per_camera_table(
            &mut out, "CAMERA TOTAL", "(pre_send_ns − dequeue_ns)",
            &per_camera_schema, &totals, &totals, &camera_labels,
        );

        // Per-camera corner counts (not time values — print separately)
        out.push_str("  > CORNERS DETECTED  (per frame)\n");
        let max_label_len = stats.cameras.iter()
            .map(|c| c.camera_id.len()).max().unwrap_or(0).max(26);
        let corner_schema = TableSchema {
            name_w: max_label_len,
            cell_widths: vec![10, 10, 10, 6, 8, 4],
        };
        corner_schema.print_header(&mut out, "Camera", &["Median", "Mean", "Std", "CV%", "% total", "n"]);
        corner_schema.print_separator(&mut out);
        for cam in &stats.cameras {
            let corner_f64: Vec<f64> = cam.corners_detected.iter().map(|&n| n as f64).collect();
            if let Some(s) = compute_stats(&corner_f64) {
                let cells = vec![
                    format!("{:.0}", s.median),
                    format!("{:.1}", s.mean),
                    format!("{:.1}", s.std),
                    fmt_pct(s.cv_pct),
                    "—".to_string(),
                    s.n.to_string(),
                ];
                corner_schema.print_row(&mut out, &cam.camera_id, &cells);
            }
        }
        out.push('\n');
    }

    // ── 5. Aggregator ──
    print_summary_table(&mut out, "AGGREGATOR", &[
        ("Collection", &stats.aggregator.collection_ns),
        ("Triangulation", &stats.aggregator.triangulation_ns),
        ("Filtering", &stats.aggregator.filtering_ns),
        ("Output publish", &stats.aggregator.output_publish_ns),
        ("Total aggregator", &stats.aggregator.total_ns),
    ]);

    out.push_str("═══════════════════════════════════════════════════════════════════════════════\n");
    out.push('\n');

    tracing::info!("{}", out);
}
