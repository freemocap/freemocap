//! Video dispatcher thread — reads synchronized frames from video files,
//! encodes them as JPEG, and writes to FrameSlots (the same output interface
//! that CameraGroup's dispatcher uses).
//!
//! This is the video equivalent of skellycam's dispatcher thread. Rather than
//! receiving `MultiFramePayload` from a gatherer (which synchronizes live
//! cameras via BreakableBarrier), the video dispatcher reads frames directly
//! from `VideoReader`s in lockstep. Frame sync is guaranteed by sequential
//! `read()` on all readers — no barrier needed.
//!
//! ## Pacing
//!
//! When `pacing_signal` is `Some(Arc<AtomicI64>)`, the dispatcher shares this
//! atomic with the distributor. The distributor writes the last consumed
//! frame_number after each pipeline cycle. The dispatcher checks this before
//! writing frame N+1 — if the distributor hasn't consumed frame N yet, the
//! dispatcher sleeps. This prevents frame dropping.
//!
//! When `pacing_signal` is `None`, the dispatcher writes frames as fast as
//! they can be read from disk — the pipeline skips whatever it can't keep
//! up with (matching real-time behavior).

use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use opencv::core::Vector;
use opencv::imgcodecs;

use skellycam::camera::types::FrameLifecycleTimestamps;
use skellycam::camera_group::dispatcher::{FrontendPayload, RawFrame};
use skellycam::timestamps::performance::performance_counter_nanoseconds;

use crate::pipeline::stats::VideoDispatcherStats;
use crate::pipeline::types::VideoFrameTimestamps;

use super::reader::VideoReader;

/// Spawn the video dispatcher thread.
///
/// Reads frames sequentially from all readers, encodes BGR→JPEG, packages as
/// `RawFrame` + `FrontendPayload`, and writes to `FrameSlots`. Also populates
/// `video_timestamps_slot` with per-multiframe video-read timing data.
///
/// # Arguments
/// * `readers` — one per camera, already opened and validated.
/// * `camera_ids` — names matching the calibration (e.g. "Cam1", "Cam2", "Cam3").
/// * `raw_frames_slot` — FrameSlots.raw_frames — shared slot for `Vec<RawFrame>`.
/// * `frontend_payload_slot` — FrameSlots.frontend_payload.
/// * `video_timestamps_slot` — per-multiframe video timestamps for observability.
/// * `shutdown_flag` — set to true to stop the dispatcher.
/// * `pacing_signal` — optional shared atomic for consumption backpressure.
///   The distributor writes the last consumed frame_number; the dispatcher
///   checks it to avoid overwriting unprocessed frames.
/// * `max_frames` — optional cap for test runs (None = process all frames).
/// * `stats_out` — written with per-frame timing data before thread exit.
pub fn spawn_video_dispatcher(
    mut readers: Vec<VideoReader>,
    camera_ids: Vec<String>,
    raw_frames_slot: Arc<Mutex<Option<Vec<RawFrame>>>>,
    frontend_payload_slot: Arc<Mutex<Option<FrontendPayload>>>,
    video_timestamps_slot: Arc<Mutex<Option<VideoFrameTimestamps>>>,
    shutdown_flag: Arc<AtomicBool>,
    pacing_signal: Option<Arc<AtomicI64>>,
    max_frames: Option<usize>,
    stats_out: Arc<Mutex<Option<crate::pipeline::stats::VideoDispatcherStats>>>,
) -> JoinHandle<()> {
    assert_eq!(
        readers.len(),
        camera_ids.len(),
        "readers and camera_ids must have same length"
    );
    assert!(!readers.is_empty(), "at least one reader required");

    let n_cameras = readers.len();
    let video_fps = readers[0].fps();

    // Capture per-camera dimensions before moving readers into the thread.
    let cam_widths: Vec<u32> = readers.iter().map(|r| r.width()).collect();
    let cam_heights: Vec<u32> = readers.iter().map(|r| r.height()).collect();

    thread::Builder::new()
        .name("video-dispatcher".into())
        .spawn(move || {
            let mut stats = VideoDispatcherStats::default();
            let mut frame_number: i64 = 0;

            loop {
                if shutdown_flag.load(Ordering::Relaxed) {
                    tracing::info!("[video-dispatcher] shutdown flag set, exiting");
                    break;
                }

                if let Some(max) = max_frames {
                    if frame_number as usize >= max {
                        tracing::info!(
                            "[video-dispatcher] reached max_frames={}, exiting",
                            max
                        );
                        break;
                    }
                }

                // ── Pacing: wait for distributor to consume previous frame ──
                if let Some(ref signal) = pacing_signal {
                    let consumed = signal.load(Ordering::SeqCst);
                    if frame_number > 0 && consumed < frame_number - 1 {
                        // Distributor hasn't consumed frame N-1 yet —
                        // brief sleep then retry without advancing frame_number.
                        thread::sleep(Duration::from_millis(1));
                        continue;
                    }
                }

                // ── Read one frame from each video ──
                let video_read_start_ns = performance_counter_nanoseconds();

                let mut bgr_frames = Vec::with_capacity(n_cameras);
                let mut all_ok = true;
                for (i, reader) in readers.iter_mut().enumerate() {
                    match reader.read_next() {
                        Some(Ok(frame)) => bgr_frames.push(frame),
                        Some(Err(e)) => {
                            tracing::warn!(
                                "[video-dispatcher] read error cam={} frame={}: {}",
                                camera_ids[i], frame_number, e
                            );
                            all_ok = false;
                            break;
                        }
                        None => {
                            tracing::debug!(
                                "[video-dispatcher] EOF cam={} frame={}",
                                camera_ids[i], frame_number
                            );
                            all_ok = false;
                            break;
                        }
                    }
                }

                if !all_ok {
                    break;
                }

                let video_read_done_ns = performance_counter_nanoseconds();

                // ── Encode BGR → JPEG for each camera ──
                // Quality 95 matches real camera MJPEG output.
                let mut jpeg_frames: Vec<(Vec<u8>, u32, u32)> =
                    Vec::with_capacity(n_cameras);

                for (i, bgr) in bgr_frames.iter().enumerate() {
                    let mut jpeg_buf = Vector::<u8>::new();
                    let mut encode_params = Vector::<i32>::new();
                    encode_params.push(imgcodecs::IMWRITE_JPEG_QUALITY);
                    encode_params.push(100); // max quality so charuco detection isn't degraded
                    match imgcodecs::imencode(".jpg", bgr, &mut jpeg_buf, &encode_params) {
                        Ok(_) => {
                            let bytes: Vec<u8> = jpeg_buf.into_iter().collect();
                            jpeg_frames.push((bytes, cam_widths[i], cam_heights[i]));
                        }
                        Err(_) => {
                            tracing::warn!(
                                "[video-dispatcher] JPEG encode failed frame={}",
                                frame_number
                            );
                            jpeg_frames.push((Vec::new(), 0, 0));
                        }
                    }
                }

                let video_encode_done_ns = performance_counter_nanoseconds();

                // ── Build RawFrame per camera ──
                let raw_frames: Vec<RawFrame> = camera_ids
                    .iter()
                    .enumerate()
                    .map(|(i, cam_id)| {
                        let (ref jpeg_bytes, w, h) = jpeg_frames[i];
                        RawFrame {
                            camera_id: cam_id.clone(),
                            camera_index: i as i32,
                            width: w,
                            height: h,
                            jpeg_bytes: jpeg_bytes.clone().into(),
                            frame_number,
                            timestamps: FrameLifecycleTimestamps::new(),
                        }
                    })
                    .collect();

                // ── Build FrontendPayload ──
                let synthetic_timestamp_ns = if video_fps > 0.0 {
                    (frame_number as f64 / video_fps) * 1_000_000_000.0
                } else {
                    0.0
                };
                let frontend = FrontendPayload {
                    frame_number,
                    timestamp_ns: synthetic_timestamp_ns,
                    camera_fps: video_fps,
                    jpeg_bytes: Vec::new(),
                };

                let video_payload_built_ns = performance_counter_nanoseconds();

                // ── Build video timestamps ──
                let video_ts = VideoFrameTimestamps {
                    video_read_start_ns,
                    video_read_done_ns,
                    video_encode_done_ns,
                    video_payload_built_ns,
                    video_slots_written_ns: 0,
                };

                // ── Write to FrameSlots ──
                {
                    if let Ok(mut guard) = raw_frames_slot.lock() {
                        *guard = Some(raw_frames);
                    }
                    if let Ok(mut guard) = frontend_payload_slot.lock() {
                        *guard = Some(frontend);
                    }
                }

                let video_slots_written_ns = performance_counter_nanoseconds();

                // ── Write video timestamps ──
                if let Ok(mut guard) = video_timestamps_slot.lock() {
                    *guard = Some(VideoFrameTimestamps {
                        video_slots_written_ns,
                        ..video_ts
                    });
                }

                // ── Record stats ──
                stats.read_ns.push((video_read_done_ns - video_read_start_ns) as f64);
                stats.encode_ns.push((video_encode_done_ns - video_read_done_ns) as f64);
                stats.payload_build_ns.push((video_payload_built_ns - video_encode_done_ns) as f64);
                stats.slots_write_ns.push((video_slots_written_ns - video_payload_built_ns) as f64);
                stats.total_ns.push((video_slots_written_ns - video_read_start_ns) as f64);

                frame_number += 1;
            }

            // ── Publish stats ──
            if let Ok(mut guard) = stats_out.lock() {
                *guard = Some(stats);
            }

            tracing::info!(
                "[video-dispatcher] exiting after {} frames",
                frame_number
            );
        })
        .expect("Failed to spawn video dispatcher thread")
}
