use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::{self, Receiver},
    Arc, RwLock,
};

use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::camera_group::FrameSlots;
use skellycam::timestamps::performance::performance_counter_nanoseconds;

use super::config::PipelineConfig;
use super::types::{DistributorSlot, PerCameraFrameData, PipelineTimestamps};

/// Commands the distributor can receive from the pipeline manager.
#[derive(Debug, Clone)]
pub enum PipelineCommand {
    UpdateConfig(PipelineConfig),
    Shutdown,
}

/// State owned by the distributor thread.
pub struct Distributor {
    /// Barrier with count = N_cameras + 1. Distributor participates.
    pub barrier: Arc<BreakableBarrier>,
    /// Slot written by distributor, read by all camera nodes.
    pub slot: Arc<RwLock<DistributorSlot>>,
    /// Command receiver — config updates and shutdown.
    pub cmd_rx: Receiver<PipelineCommand>,
    /// Shared frame slots from the CameraGroup's dispatcher.
    /// The distributor polls these directly — same Arc that the CameraGroup uses.
    pub frame_slots: FrameSlots,
    /// Shutdown flag — set by main thread.
    pub shutdown_flag: Arc<AtomicBool>,
}

impl Distributor {
    pub fn new(
        barrier: Arc<BreakableBarrier>,
        slot: Arc<RwLock<DistributorSlot>>,
        cmd_rx: Receiver<PipelineCommand>,
        frame_slots: FrameSlots,
        shutdown_flag: Arc<AtomicBool>,
    ) -> Self {
        Self {
            barrier,
            slot,
            cmd_rx,
            frame_slots,
            shutdown_flag,
        }
    }
}

/// Main loop for the distributor thread.
///
/// Polls the CameraGroup's shared frame slots (same `Arc<Mutex<Option<T>>>`
/// that the dispatcher thread writes to), snapshots them, writes the
/// distributor slot, and releases camera nodes via the BreakableBarrier.
/// Zero Python in the frame path.
pub fn run_distributor(distributor: Distributor) {
    let mut last_distributed: i64 = -1;

    loop {
        // ── Handle commands ──
        match distributor.cmd_rx.try_recv() {
            Ok(PipelineCommand::Shutdown) => break,
            Ok(PipelineCommand::UpdateConfig(_config)) => {}
            Err(mpsc::TryRecvError::Empty) => {}
            Err(mpsc::TryRecvError::Disconnected) => break,
        }

        if distributor.shutdown_flag.load(Ordering::Relaxed) {
            break;
        }

        // ── Poll CameraGroup's shared slots directly ──
        let raw_frames = {
            let guard = distributor.frame_slots.raw_frames.lock().unwrap();
            guard.clone()
        };
        let frontend_payload = {
            let guard = distributor.frame_slots.frontend_payload.lock().unwrap();
            guard.clone()
        };

        let raw_frames = match raw_frames {
            Some(frames) => frames,
            None => {
                std::thread::sleep(std::time::Duration::from_millis(1));
                continue;
            }
        };
        let frontend_payload = match frontend_payload {
            Some(payload) => payload,
            None => {
                std::thread::sleep(std::time::Duration::from_millis(1));
                continue;
            }
        };

        // ── Guard ──
        if raw_frames.is_empty() {
            continue;
        }
        let frame_number = raw_frames[0].frame_number;
        if frame_number != frontend_payload.frame_number {
            tracing::error!(
                "[freemocap::distributor] frame_number mismatch: raw={} payload={}",
                frame_number,
                frontend_payload.frame_number
            );
            continue;
        }

        if frame_number <= last_distributed {
            std::thread::sleep(std::time::Duration::from_millis(1));
            continue;
        }

        // ── Write shared slot ──
        let distributor_slot_write_ns = performance_counter_nanoseconds();
        {
            let mut slot = distributor.slot.write().unwrap();
            slot.frame_number = frame_number;
            slot.timestamp_ns = frontend_payload.timestamp_ns;
            slot.camera_fps = frontend_payload.camera_fps;
            slot.frontend_payload_bytes = frontend_payload.jpeg_bytes.clone();
            slot.per_camera_data = raw_frames
                .iter()
                .map(|rf| PerCameraFrameData {
                    camera_id: rf.camera_id.clone(),
                    jpeg_bytes: rf.jpeg_bytes.to_vec(),
                    skellycam_timestamps: rf.timestamps.clone(),
                })
                .collect();
        }

        // ── Release camera nodes ──
        let distributor_barrier_release_ns = performance_counter_nanoseconds();
        if !distributor.barrier.wait() {
            break;
        }

        // ── Stamp distributor timestamps ──
        {
            let mut slot = distributor.slot.write().unwrap();
            slot.distributor_timestamps = PipelineTimestamps {
                distributor_slot_write_ns,
                distributor_barrier_release_ns,
                ..Default::default()
            };
        }

        last_distributed = frame_number;
    }

    distributor.barrier.break_barrier();
}
