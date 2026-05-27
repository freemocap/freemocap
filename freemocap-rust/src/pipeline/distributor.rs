use std::sync::{
    atomic::{AtomicBool, AtomicI64, Ordering},
    mpsc::{self, Receiver},
    Arc, Mutex, RwLock,
};

use skellycam::camera::types::MultiFramePayload;
use skellycam::camera_group::sync_utils::BreakableBarrier;
use skellycam::camera_group::FrameSlots;
use skellycam::timestamps::performance::performance_counter_nanoseconds;

use super::config::PipelineConfig;
use super::stats::DistributorStats;
use super::types::{
    DistributorSlot, DistributorTimestamps, PerCameraFrameData, SourceFrameTimestamps,
    VideoFrameTimestamps,
};

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
    /// Optional video timestamps slot — written by VideoGroup's dispatcher,
    /// read by the distributor alongside FrameSlots.
    /// `None` when the source is a live CameraGroup.
    pub video_timestamps_slot: Option<Arc<Mutex<Option<VideoFrameTimestamps>>>>,
    /// Optional pacing signal — when present, the distributor writes the
    /// last consumed frame_number here after writing DistributorSlot.
    /// The VideoGroup dispatcher reads this to implement backpressure:
    /// it won't write frame N+1 until the distributor has consumed frame N.
    /// `None` when the source is a live CameraGroup (no pacing needed).
    pub last_consumed_frame: Option<Arc<AtomicI64>>,
    /// Video source input — receives `MultiFramePayload` from the video
    /// dispatcher via an unbounded mpsc channel. When present, the
    /// distributor uses `recv()` instead of polling `frame_slots`.
    /// `None` when the source is a live CameraGroup.
    pub video_rx: Option<Receiver<MultiFramePayload>>,
    /// Shutdown flag — set by main thread.
    pub shutdown_flag: Arc<AtomicBool>,
}

impl Distributor {
    pub fn new(
        barrier: Arc<BreakableBarrier>,
        slot: Arc<RwLock<DistributorSlot>>,
        cmd_rx: Receiver<PipelineCommand>,
        frame_slots: FrameSlots,
        video_timestamps_slot: Option<Arc<Mutex<Option<VideoFrameTimestamps>>>>,
        last_consumed_frame: Option<Arc<AtomicI64>>,
        video_rx: Option<Receiver<MultiFramePayload>>,
        shutdown_flag: Arc<AtomicBool>,
    ) -> Self {
        Self {
            barrier,
            slot,
            cmd_rx,
            frame_slots,
            video_timestamps_slot,
            last_consumed_frame,
            video_rx,
            shutdown_flag,
        }
    }
}

/// Main loop for the distributor thread.
///
/// Returns per-frame timing statistics.
pub fn run_distributor(distributor: Distributor) -> DistributorStats {
    let mut stats = DistributorStats::default();
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

        let cycle_start_ns = performance_counter_nanoseconds();

        let (raw_frames, frontend_payload, video_ts) =
            if let Some(ref rx) = distributor.video_rx {
                // ── Video source: blocking receive from mpsc channel ──
                match rx.recv() {
                    Ok(payload) => {
                        // Convert FramePacket → RawFrame-like data
                        let raws: Vec<skellycam::camera_group::dispatcher::RawFrame> = payload
                            .frames
                            .iter()
                            .map(|fp| {
                                skellycam::camera_group::dispatcher::RawFrame {
                                    camera_id: fp.identity.camera_id.clone(),
                                    camera_index: fp.identity.camera_index,
                                    width: fp.width,
                                    height: fp.height,
                                    jpeg_bytes: fp.data.as_bytes().to_vec().into(),
                                    frame_number: fp.frame_number,
                                    timestamps: fp.timestamps.clone(),
                                }
                            })
                            .collect();
                        let frontend = skellycam::camera_group::dispatcher::FrontendPayload {
                            frame_number: payload.frame_number,
                            timestamp_ns: 0.0,
                            camera_fps: 0.0,
                            jpeg_bytes: Vec::new(),
                        };
                        // Extract video timestamps from side-channel
                        let vts = distributor
                            .video_timestamps_slot
                            .as_ref()
                            .and_then(|slot| slot.lock().ok())
                            .and_then(|guard| guard.clone());
                        (raws, frontend, vts)
                    }
                    Err(_) => break, // channel disconnected → shutdown
                }
            } else {
                // ── Camera source: poll FrameSlots ──
                let raw = {
                    let guard = distributor.frame_slots.raw_frames.lock().unwrap();
                    guard.clone()
                };
                let payload = {
                    let guard = distributor.frame_slots.frontend_payload.lock().unwrap();
                    guard.clone()
                };

                let raw = match raw {
                    Some(frames) => frames,
                    None => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                        continue;
                    }
                };
                let payload = match payload {
                    Some(p) => p,
                    None => {
                        std::thread::sleep(std::time::Duration::from_millis(1));
                        continue;
                    }
                };

                if raw.is_empty() {
                    tracing::trace!("[freemocap::distributor] raw_frames empty, sleeping");
                    continue;
                }
                let fnr = raw[0].frame_number;
                if fnr != payload.frame_number {
                    tracing::error!(
                        "[freemocap::distributor] frame_number mismatch: raw={} payload={}",
                        fnr, payload.frame_number
                    );
                    continue;
                }
                if fnr <= last_distributed {
                    std::thread::sleep(std::time::Duration::from_millis(1));
                    continue;
                }
                (raw, payload, None)
            };

        // ── Guard ──
        if raw_frames.is_empty() {
            continue;
        }
        let frame_number = raw_frames[0].frame_number;

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
                .map(|rf| {
                    let source_ts = match &video_ts {
                        Some(_vt) => {
                            SourceFrameTimestamps::Video(video_ts.clone().unwrap())
                        }
                        None => {
                            SourceFrameTimestamps::Camera(rf.timestamps.clone())
                        }
                    };
                    PerCameraFrameData {
                        camera_id: rf.camera_id.clone(),
                        jpeg_bytes: rf.jpeg_bytes.to_vec(),
                        source_timestamps: source_ts,
                    }
                })
                .collect();
        }

        tracing::trace!(
            "[freemocap::distributor] wrote slot frame={} n_cameras={}",
            frame_number,
            raw_frames.len(),
        );

        // ── Release camera nodes ──
        let distributor_barrier_release_ns = performance_counter_nanoseconds();
        if !distributor.barrier.wait() {
            tracing::info!("[freemocap::distributor] barrier broken, shutting down");
            break;
        }
        let post_barrier_ns = performance_counter_nanoseconds();

        // ── Stamp distributor timestamps ──
        {
            let mut slot = distributor.slot.write().unwrap();
            slot.distributor_timestamps = DistributorTimestamps {
                cycle_start_ns,
                slot_write_done_ns: distributor_slot_write_ns,
                barrier_release_ns: distributor_barrier_release_ns,
                barrier_return_ns: post_barrier_ns,
            };
        }

        // ── Record stats ──
        stats.slot_work_ns.push((distributor_slot_write_ns - cycle_start_ns) as f64);
        stats.barrier_wait_ns.push((post_barrier_ns - distributor_barrier_release_ns) as f64);
        stats.total_ns.push((post_barrier_ns - cycle_start_ns) as f64);

        // Signal consumption for dispatcher pacing (video source only).
        if let Some(ref consumed) = distributor.last_consumed_frame {
            consumed.store(frame_number, Ordering::SeqCst);
        }

        last_distributed = frame_number;
    }

    tracing::info!(
        "[freemocap::distributor] shutting down ({} frames)",
        stats.total_ns.len()
    );
    distributor.barrier.break_barrier();
    stats
}
