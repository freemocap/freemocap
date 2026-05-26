//! One Euro filter: adaptive low-pass filter with velocity-dependent cutoff.
//!
//! Based on: Géry Casiez, "1€ Filter: A Simple Speed-based Low-pass Filter for
//! Noisy Input in Interactive Systems" (CHI 2012).
//!
//! The cutoff frequency adapts to the signal's rate of change:
//!   cutoff = min_cutoff + beta * |velocity|
//! At rest (velocity ≈ 0), cutoff = min_cutoff (heavy smoothing).
//! During motion (velocity ↑), cutoff rises (more responsive, less lag).

use std::collections::HashMap;

/// Smoothing factor for exponential moving average.
///
/// alpha = (2π * cutoff * dt) / (2π * cutoff * dt + 1)
fn smoothing_factor(dt: f64, cutoff: f64) -> f64 {
    let r = 2.0 * std::f64::consts::PI * cutoff * dt;
    r / (r + 1.0)
}

/// Single-axis One Euro filter.
/// Maintains filtered value and filtered velocity between frames.
#[derive(Debug, Clone)]
struct OneEuroFilter1D {
    x_prev: f64,
    dx_prev: f64,
    t_prev: f64,
}

impl OneEuroFilter1D {
    fn new(t0: f64, x0: f64, dx0: f64) -> Self {
        Self {
            x_prev: x0,
            dx_prev: dx0,
            t_prev: t0,
        }
    }

    /// Filter the next value. Returns the filtered result.
    fn filter(
        &mut self,
        t: f64,
        x: f64,
        min_cutoff: f64,
        beta: f64,
        d_cutoff: f64,
    ) -> f64 {
        let dt = t - self.t_prev;
        if dt <= 0.0 {
            return x; // non-increasing timestamp — return raw
        }

        // Step 1: Filter the derivative (velocity)
        let alpha_d = smoothing_factor(dt, d_cutoff);
        let dx = (x - self.x_prev) / dt;
        let dx_hat = alpha_d * dx + (1.0 - alpha_d) * self.dx_prev;

        // Step 2: Adaptive cutoff
        let cutoff = min_cutoff + beta * dx_hat.abs();

        // Step 3: Filter the signal
        let alpha = smoothing_factor(dt, cutoff);
        let x_hat = alpha * x + (1.0 - alpha) * self.x_prev;

        // Step 4: Update state
        self.x_prev = x_hat;
        self.dx_prev = dx_hat;
        self.t_prev = t;

        x_hat
    }

    /// Predict the next value (for gap filling).
    /// Velocity decays toward zero each prediction step.
    fn predict(&mut self, t: f64, velocity_decay: f64) -> f64 {
        let dt = t - self.t_prev;
        if dt <= 0.0 {
            return self.x_prev;
        }
        let x_pred = self.x_prev + self.dx_prev * dt;
        self.x_prev = x_pred;
        self.dx_prev *= velocity_decay;
        self.t_prev = t;
        x_pred
    }
}

/// 3D One Euro filter — three independent 1D filters, one per axis.
#[derive(Debug, Clone)]
struct OneEuroFilter3D {
    x_filter: OneEuroFilter1D,
    y_filter: OneEuroFilter1D,
    z_filter: OneEuroFilter1D,
}

impl OneEuroFilter3D {
    fn new(t0: f64, pos: [f64; 3]) -> Self {
        Self {
            x_filter: OneEuroFilter1D::new(t0, pos[0], 0.0),
            y_filter: OneEuroFilter1D::new(t0, pos[1], 0.0),
            z_filter: OneEuroFilter1D::new(t0, pos[2], 0.0),
        }
    }

    fn filter(
        &mut self,
        t: f64,
        pos: [f64; 3],
        min_cutoff: f64,
        beta: f64,
        d_cutoff: f64,
    ) -> [f64; 3] {
        [
            self.x_filter.filter(t, pos[0], min_cutoff, beta, d_cutoff),
            self.y_filter.filter(t, pos[1], min_cutoff, beta, d_cutoff),
            self.z_filter.filter(t, pos[2], min_cutoff, beta, d_cutoff),
        ]
    }

    fn predict(&mut self, t: f64, velocity_decay: f64) -> [f64; 3] {
        [
            self.x_filter.predict(t, velocity_decay),
            self.y_filter.predict(t, velocity_decay),
            self.z_filter.predict(t, velocity_decay),
        ]
    }
}

/// Per-keypoint One Euro filter bank with gap-filling prediction.
///
/// Maintains one `OneEuroFilter3D` per keypoint name. On frames where a
/// keypoint is missing, predicts its position using the stored velocity
/// (with exponential decay) for up to `max_prediction_frames` consecutive
/// frames before dropping the keypoint entirely.
pub struct OneEuroFilter {
    filters: HashMap<String, OneEuroFilter3D>,
    prediction_counts: HashMap<String, u32>,
    last_t: Option<f64>,
    min_cutoff: f64,
    beta: f64,
    d_cutoff: f64,
    max_prediction_frames: u32,
    prediction_velocity_decay: f64,
}

impl OneEuroFilter {
    pub fn new(min_cutoff: f64, beta: f64, d_cutoff: f64) -> Self {
        Self {
            filters: HashMap::new(),
            prediction_counts: HashMap::new(),
            last_t: None,
            min_cutoff,
            beta,
            d_cutoff,
            max_prediction_frames: 3,
            prediction_velocity_decay: 0.5,
        }
    }

    pub fn set_params(&mut self, min_cutoff: f64, beta: f64, d_cutoff: f64) {
        self.min_cutoff = min_cutoff;
        self.beta = beta;
        self.d_cutoff = d_cutoff;
    }

    /// Filter a frame of keypoints. Returns the filtered positions.
    ///
    /// Missing keypoints (present in `filters` but not in `points`) are
    /// predicted for up to `max_prediction_frames` consecutive frames.
    pub fn filter(
        &mut self,
        t: f64,
        points: &HashMap<String, [f64; 3]>,
    ) -> HashMap<String, [f64; 3]> {
        // Non-monotonic timestamp guard
        if let Some(last) = self.last_t {
            if t <= last {
                return points.clone();
            }
        }
        self.last_t = Some(t);

        let min_names: Vec<String> = points.keys().cloned().collect();
        let mut result = HashMap::new();

        // Step 1: Process present keypoints
        for name in &min_names {
            let pos = points[name];
            self.prediction_counts.insert(name.clone(), 0);

            let filt = self.filters.entry(name.clone()).or_insert_with(|| {
                OneEuroFilter3D::new(t, pos)
            });

            let filtered = filt.filter(t, pos, self.min_cutoff, self.beta, self.d_cutoff);
            result.insert(name.clone(), filtered);
        }

        // Step 2: Predict missing keypoints
        let known_names: Vec<String> = self.filters.keys().cloned().collect();
        for name in known_names {
            if points.contains_key(&name) {
                continue; // already filtered above
            }

            let count = self.prediction_counts.get(&name).copied().unwrap_or(0);
            if count >= self.max_prediction_frames {
                continue; // drop — exceeded prediction streak
            }

            if let Some(filt) = self.filters.get_mut(&name) {
                let predicted = filt.predict(t, self.prediction_velocity_decay);
                result.insert(name.clone(), predicted);
                self.prediction_counts.insert(name, count + 1);
            }
        }

        result
    }

    /// Reset all filter state. Call when calibration changes.
    pub fn reset(&mut self) {
        self.filters.clear();
        self.prediction_counts.clear();
        self.last_t = None;
    }
}
