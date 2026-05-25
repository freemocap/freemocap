//! Velocity gate: rejects teleportation spikes by comparing consecutive
//! positions against a maximum velocity threshold.
//! Implementation deferred to next milestone — currently pass-through.

use std::collections::HashMap;

pub struct RealtimePointGate {
    pub max_velocity_m_per_s: f64,
    pub max_rejected_streak: u32,
}

impl RealtimePointGate {
    pub fn new(max_velocity_m_per_s: f64, max_rejected_streak: u32) -> Self {
        Self {
            max_velocity_m_per_s,
            max_rejected_streak,
        }
    }

    pub fn set_max_velocity(&mut self, v: f64) {
        self.max_velocity_m_per_s = v;
    }

    pub fn set_max_streak(&mut self, s: u32) {
        self.max_rejected_streak = s;
    }

    pub fn gate(
        &mut self,
        points: &HashMap<String, [f64; 3]>,
    ) -> HashMap<String, [f64; 3]> {
        points.clone()
    }
}
