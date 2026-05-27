//! Video dispatcher thread — reads synchronized frames from video files,
//! encodes them as JPEG, packages as `MultiFramePayload`, and sends them
//! down an unbounded mpsc channel to the pipeline distributor.
//!
//! This is the video equivalent of skellycam's gatherer→dispatcher pipeline.
//! Rather than receiving `MultiFramePayload` from a gatherer, the video
//! dispatcher reads frames directly from `VideoReader`s in lockstep and
//! produces the same `MultiFramePayload` type. Frame sync is guaranteed by
//! sequential `read()` on all readers — no barrier needed.
//!
//! ## Backpressure
//!
//! The unbounded mpsc channel provides natural backpressure: the dispatcher
//! sends frames as fast as it reads them, and the pipeline distributor
//! receives at its own rate. If the pipeline is slower, frames buffer in
//! the channel (unbounded — no frame dropping). No pacing signal needed.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::Sender;
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};

use opencv::core::Vector;
use opencv::imgcodecs;

use skellycam::camera::types::{FramePacket, GathererTimestamps, MultiFramePayload};
use skellycam::camera::CameraIdentity;
use skellycam::camera::types::{FrameData, FrameLifecycleTimestamps};
use skellycam::timestamps::performance::performance_counter_nanoseconds;

use crate::pipeline::stats::VideoDispatcherStats;
use crate::pipeline::types::VideoFrameTimestamps;

use super::reader::VideoReader;

pub fn spawn_video_dispatcher(
    mut readers: Vec<VideoReader>,
    camera_ids: Vec<String>,
    multi_frame_tx: Sender<MultiFramePayload>,
    video_timestamps_slot: Arc<Mutex<Option<VideoFrameTimestamps>>>,
    shutdown_flag: Arc<AtomicBool>,
    max_frames: Option<usize>,
    stats_out: Arc<Mutex<Option<VideoDispatcherStats>>>,
) -> JoinHandle<()> {
    assert_eq!(readers.len(), camera_ids.len());
    assert!(!readers.is_empty());

    let n_cameras = readers.len();
    let cam_widths: Vec<u32> = readers.iter().map(|r| r.width()).collect();
    let cam_heights: Vec<u32> = readers.iter().map(|r| r.height()).collect();

    // Build CameraIdentity per camera (video source — no device path)
    let identities: Vec<CameraIdentity> = camera_ids
        .iter()
        .enumerate()
        .map(|(i, id)| CameraIdentity {
            camera_name: id.clone(),
            camera_index: i as i32,
            camera_id: id.clone(),
            device_path: String::new(),
            formats: Vec::new(),
        })
        .collect();

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
                        tracing::info!("[video-dispatcher] reached max_frames={max}, exiting");
                        break;
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
                            tracing::warn!("[video-dispatcher] read error cam={} frame={frame_number}: {e}", camera_ids[i]);
                            all_ok = false; break;
                        }
                        None => { all_ok = false; break; }
                    }
                }
                if !all_ok { break; }
                let video_read_done_ns = performance_counter_nanoseconds();

                // ── Encode BGR → JPEG per camera ──
                let mut jpeg_frames: Vec<(Vec<u8>, u32, u32)> = Vec::with_capacity(n_cameras);
                for (i, bgr) in bgr_frames.iter().enumerate() {
                    let mut jpeg_buf = Vector::<u8>::new();
                    let mut params = Vector::<i32>::new();
                    params.push(imgcodecs::IMWRITE_JPEG_QUALITY);
                    params.push(95);
                    match imgcodecs::imencode(".jpg", bgr, &mut jpeg_buf, &params) {
                        Ok(_) => jpeg_frames.push((
                            jpeg_buf.into_iter().collect(),
                            cam_widths[i], cam_heights[i],
                        )),
                        Err(_) => jpeg_frames.push((Vec::new(), 0, 0)),
                    }
                }
                let video_encode_done_ns = performance_counter_nanoseconds();

                // ── Build FramePacket per camera ──
                let frame_packets: Vec<FramePacket> = camera_ids
                    .iter()
                    .enumerate()
                    .map(|(i, _)| {
                        let (ref jpeg, w, h) = jpeg_frames[i];
                        FramePacket {
                            data: FrameData::Mjpg(jpeg.clone()),
                            width: w,
                            height: h,
                            rotation: 0,
                            timestamps: FrameLifecycleTimestamps::new(),
                            identity: identities[i].clone(),
                            frame_number,
                        }
                    })
                    .collect();

                // ── Build gatherer timestamps (video semantics) ──
                let gatherer_ts = GathererTimestamps {
                    collecting_start_ns: video_read_start_ns,
                    all_frames_received_ns: video_read_done_ns,
                    post_barrier_ns: 0, // no barrier for video
                    payload_assembled_ns: video_encode_done_ns,
                    pre_send_downstream_ns: performance_counter_nanoseconds(),
                };

                let video_payload_built_ns = performance_counter_nanoseconds();

                // ── Build MultiFramePayload ──
                let payload = MultiFramePayload {
                    frames: frame_packets,
                    frame_number,
                    gatherer_timestamps: gatherer_ts,
                };

                // ── Send downstream ──
                if multi_frame_tx.send(payload).is_err() {
                    tracing::info!("[video-dispatcher] downstream disconnected, exiting");
                    break;
                }

                let video_slots_written_ns = performance_counter_nanoseconds();

                // ── Write video timestamps for observability ──
                if let Ok(mut guard) = video_timestamps_slot.lock() {
                    *guard = Some(VideoFrameTimestamps {
                        video_read_start_ns,
                        video_read_done_ns,
                        video_encode_done_ns,
                        video_payload_built_ns,
                        video_slots_written_ns,
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

            if let Ok(mut guard) = stats_out.lock() {
                *guard = Some(stats);
            }
            tracing::info!("[video-dispatcher] exiting after {frame_number} frames");
        })
        .expect("Failed to spawn video dispatcher thread")
}
