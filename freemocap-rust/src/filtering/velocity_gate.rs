//! Velocity gate: rejects teleportation spikes by comparing consecutive
//! positions against a maximum velocity threshold.
//!
//! For each point, the gate computes `|pos_new - pos_prev| / dt` and
//! rejects the point if it exceeds `max_velocity_m_per_s`. Rejected points
//! get their last accepted position (the reference does NOT move — this
//! prevents a single garbage spike from permanently shifting the reference).
//!
//! After `max_rejected_streak` consecutive rejections, the gate accepts
//! unconditionally to break out of a potential lockout.

use std::collections::HashMap;

pub struct RealtimePointGate {
    max_velocity_m_per_s: f64,
    max_rejected_streak: u32,
    accepted: HashMap<String, [f64; 3]>,
    streaks: HashMap<String, u32>,
    previous_t: Option<f64>,
}

impl RealtimePointGate {
    pub fn new(max_velocity_m_per_s: f64, max_rejected_streak: u32) -> Self {
        Self {
            max_velocity_m_per_s,
            max_rejected_streak,
            accepted: HashMap::new(),
            streaks: HashMap::new(),
            previous_t: None,
        }
    }

    pub fn set_max_velocity(&mut self, v: f64) {
        self.max_velocity_m_per_s = v;
    }

    pub fn set_max_streak(&mut self, s: u32) {
        self.max_rejected_streak = s;
    }

    /// Gate a frame of 3D points. Returns the gated positions (with rejected
    /// points held at their last accepted position).
    pub fn gate(
        &mut self,
        t: f64,
        points: &HashMap<String, [f64; 3]>,
    ) -> HashMap<String, [f64; 3]> {
        let mut result = HashMap::new();

        // Cold start — first frame: accept everything
        let dt = match self.previous_t {
            None => {
                for (name, pos) in points {
                    self.accepted.insert(name.clone(), *pos);
                    self.streaks.insert(name.clone(), 0);
                    result.insert(name.clone(), *pos);
                }
                self.previous_t = Some(t);
                return result;
            }
            Some(prev) => t - prev,
        };

        if dt <= 0.0 {
            return points.clone();
        }

        for (name, pos) in points {
            // Never-before-seen point: accept unconditionally
            let last_accepted = match self.accepted.get(name) {
                Some(p) => *p,
                None => {
                    self.accepted.insert(name.clone(), *pos);
                    self.streaks.insert(name.clone(), 0);
                    result.insert(name.clone(), *pos);
                    continue;
                }
            };

            // Stale point: accept unconditionally (prevent permanent lockout)
            let streak = self.streaks.get(name).copied().unwrap_or(0);
            if streak >= self.max_rejected_streak {
                self.accepted.insert(name.clone(), *pos);
                self.streaks.insert(name.clone(), 0);
                result.insert(name.clone(), *pos);
                continue;
            }

            // Compute velocity
            let dx = pos[0] - last_accepted[0];
            let dy = pos[1] - last_accepted[1];
            let dz = pos[2] - last_accepted[2];
            let distance = (dx * dx + dy * dy + dz * dz).sqrt();
            let velocity = distance / dt;

            if velocity <= self.max_velocity_m_per_s {
                // Accept: reference moves forward
                self.accepted.insert(name.clone(), *pos);
                self.streaks.insert(name.clone(), 0);
                result.insert(name.clone(), *pos);
            } else {
                // Reject: hold at last accepted, reference does NOT move
                result.insert(name.clone(), last_accepted);
                self.streaks.insert(name.clone(), streak + 1);
            }
        }

        self.previous_t = Some(t);
        result
    }

    /// Reset all state. Call when calibration changes.
    pub fn reset(&mut self) {
        self.accepted.clear();
        self.streaks.clear();
        self.previous_t = None;
    }
}
