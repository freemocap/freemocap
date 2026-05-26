//! Synchronized multi-camera video playback — a CameraGroup-compatible data
//! source for the real-time pipeline.
//!
//! `VideoGroup` opens N video files and produces `FrameSlots` output
//! isomorphic to `CameraGroup`, so the pipeline distributor can consume
//! video files without knowing whether frames come from live cameras or disk.
//!
//! ## Architecture
//!
//! ```text
//! VideoReader[0..N] ──→ VideoDispatcher (thread) ──→ FrameSlots
//!                           │                            │
//!                           │ BGR→JPEG encode            │ Same Arc<Mutex<Option<T>>>
//!                           │ build RawFrame +           │ as CameraGroup
//!                           │ FrontendPayload            │
//!                           │                            │
//!                           └──→ video_timestamps_slot   │
//! ```
//!
//! The dispatcher reads frames from all videos in lockstep, JPEG-encodes,
//! and writes to `FrameSlots` — the exact same output type that skellycam's
//! dispatcher produces. The pipeline distributor polls these slots identically.
//!
//! ## Sync Guarantee
//!
//! `VideoCapture::read()` advances the internal frame counter by exactly 1
//! each call. As long as we never call `set(CAP_PROP_POS_FRAMES, n)`, the
//! N readers stay perfectly synchronized. No `BreakableBarrier` needed —
//! sequential reads guarantee all cameras are at the same frame number.

pub mod dispatcher;
pub mod reader;

use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use skellycam::camera_group::dispatcher::{FrontendPayload, RawFrame};
use skellycam::camera_group::FrameSlots;

use crate::pipeline::types::VideoFrameTimestamps;

use reader::VideoReader;

// ── Lifecycle state ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VideoGroupState {
    /// Readers opened and validated, dispatcher not yet started.
    Created,
    /// Dispatcher thread running, frames flowing to FrameSlots.
    Streaming,
    /// Shutdown initiated, dispatcher unwinding.
    ShuttingDown,
    /// Dispatcher joined, all resources freed. Terminal state.
    Stopped,
}

// ── VideoGroup handle ────────────────────────────────────────────────────

/// A synchronized group of video files producing `FrameSlots` output.
///
/// # State lifecycle
///
/// ```text
/// Created ── start() ──→ Streaming ── shutdown() ──→ ShuttingDown ──→ Stopped
/// ```
///
/// # Example
///
/// ```ignore
/// let mut group = VideoGroup::open(
///     &["cam1.mp4", "cam2.mp4", "cam3.mp4"],
///     &["Cam1", "Cam2", "Cam3"],
/// )?;
/// group.start(true, None)?;  // paced, all frames
/// let slots = group.frame_slots();
/// // ... pass slots to pipeline distributor ...
/// group.shutdown()?;
/// ```
pub struct VideoGroup {
    group_id: String,
    state: VideoGroupState,
    readers: Vec<VideoReader>,
    camera_ids: Vec<String>,
    frame_count: i32,

    // Dispatcher
    dispatcher_handle: Option<JoinHandle<()>>,
    shutdown_flag: Arc<AtomicBool>,

    // Output slots — same types as CameraGroup
    latest_raw_frames: Arc<Mutex<Option<Vec<RawFrame>>>>,
    latest_frontend_payload: Arc<Mutex<Option<FrontendPayload>>>,

    /// Per-multiframe video-read timestamps for observability.
    /// Written by the dispatcher, read by the distributor (via
    /// `Distributor.video_timestamps_slot`).
    video_timestamps_slot: Arc<Mutex<Option<VideoFrameTimestamps>>>,
}

impl VideoGroup {
    /// Open a set of video files and verify they all have the same frame count.
    ///
    /// Returns a `VideoGroup` in the `Created` state. Call `start()` to begin
    /// frame delivery.
    pub fn open(
        paths: &[impl AsRef<std::path::Path>],
        camera_ids: &[String],
    ) -> Result<Self, String> {
        if paths.is_empty() {
            return Err("No video paths provided".into());
        }
        if paths.len() != camera_ids.len() {
            return Err(format!(
                "Number of paths ({}) does not match number of camera_ids ({})",
                paths.len(),
                camera_ids.len()
            ));
        }

        let mut readers = Vec::with_capacity(paths.len());
        let mut frame_count: Option<i32> = None;

        for path in paths {
            let reader = VideoReader::open(path)?;
            match frame_count {
                None => frame_count = Some(reader.frame_count()),
                Some(expected) if reader.frame_count() != expected => {
                    return Err(format!(
                        "Frame count mismatch: '{}' has {} frames, expected {}",
                        path.as_ref().display(),
                        reader.frame_count(),
                        expected
                    ));
                }
                _ => {}
            }
            readers.push(reader);
        }

        let fc = frame_count.unwrap_or(0);
        let group_id = uuid::Uuid::new_v4().as_simple().to_string()[..6].to_string();

        Ok(Self {
            group_id,
            state: VideoGroupState::Created,
            readers,
            camera_ids: camera_ids.to_vec(),
            frame_count: fc,
            dispatcher_handle: None,
            shutdown_flag: Arc::new(AtomicBool::new(false)),
            latest_raw_frames: Arc::new(Mutex::new(None)),
            latest_frontend_payload: Arc::new(Mutex::new(None)),
            video_timestamps_slot: Arc::new(Mutex::new(None)),
        })
    }

    /// Start the dispatcher thread. Frames begin flowing to `FrameSlots`.
    ///
    /// # Arguments
    /// * `pacing_signal` — optional shared atomic for backpressure. The
    ///   distributor writes the last consumed frame_number here. When
    ///   provided, the dispatcher waits for the distributor to consume
    ///   each frame before writing the next (no frame dropping). When
    ///   `None`, frames are written as fast as possible.
    /// * `max_frames` — optional cap (useful for tests). `None` = process all.
    ///
    /// # Errors
    /// Returns an error if not in the `Created` state.
    pub fn start(
        &mut self,
        pacing_signal: Option<Arc<AtomicI64>>,
        max_frames: Option<usize>,
    ) -> Result<(), String> {
        if self.state != VideoGroupState::Created {
            return Err(format!(
                "Cannot start VideoGroup in state {:?} — must be Created",
                self.state
            ));
        }

        let readers = std::mem::take(&mut self.readers);
        let camera_ids = self.camera_ids.clone();
        if readers.is_empty() {
            return Err("No readers — VideoGroup may have already been started".into());
        }

        tracing::info!(
            "[VideoGroup {}] starting dispatcher for {} camera(s), {} frames",
            self.group_id,
            camera_ids.len(),
            self.frame_count,
        );

        let handle = dispatcher::spawn_video_dispatcher(
            readers,
            camera_ids,
            self.latest_raw_frames.clone(),
            self.latest_frontend_payload.clone(),
            self.video_timestamps_slot.clone(),
            self.shutdown_flag.clone(),
            pacing_signal,
            max_frames,
        );

        self.dispatcher_handle = Some(handle);
        self.state = VideoGroupState::Streaming;

        tracing::info!("[VideoGroup {}] dispatcher started", self.group_id);
        Ok(())
    }

    /// Shut down the dispatcher thread and transition to `Stopped`.
    pub fn shutdown(&mut self) {
        if self.state == VideoGroupState::Stopped {
            return;
        }

        tracing::info!("[VideoGroup {}] shutting down", self.group_id);
        self.state = VideoGroupState::ShuttingDown;
        self.shutdown_flag.store(true, Ordering::SeqCst);

        if let Some(handle) = self.dispatcher_handle.take() {
            if let Err(e) = handle.join() {
                tracing::error!(
                    "[VideoGroup {}] dispatcher thread panicked: {:?}",
                    self.group_id,
                    e.downcast_ref::<&str>().unwrap_or(&"unknown panic message")
                );
            }
        }

        self.state = VideoGroupState::Stopped;
        tracing::info!("[VideoGroup {}] shutdown complete", self.group_id);
    }

    // ── Public accessors ──────────────────────────────────────────────────

    /// Return clones of the shared frame slots for external consumers.
    ///
    /// The dispatcher thread writes into these slots every multiframe. The
    /// pipeline distributor polls the same `Arc` slots. Each clone is a
    /// cheap `Arc` ref bump — same pattern as `CameraGroup::frame_slots()`.
    pub fn frame_slots(&self) -> FrameSlots {
        FrameSlots {
            raw_frames: self.latest_raw_frames.clone(),
            frontend_payload: self.latest_frontend_payload.clone(),
        }
    }

    /// Return a clone of the video timestamps slot.
    ///
    /// The distributor passes this to `Distributor.video_timestamps_slot`
    /// so it can populate `SourceFrameTimestamps::Video(...)` for each frame.
    pub fn video_timestamps_slot_arc(&self) -> Arc<Mutex<Option<VideoFrameTimestamps>>> {
        self.video_timestamps_slot.clone()
    }

    /// Whether the dispatcher is still running.
    pub fn is_alive(&self) -> bool {
        self.state == VideoGroupState::Streaming
    }

    /// Number of video streams.
    pub fn n_cameras(&self) -> usize {
        self.camera_ids.len()
    }

    /// Number of frames in each video.
    pub fn frame_count(&self) -> i32 {
        self.frame_count
    }

    /// The group's unique identifier.
    pub fn group_id(&self) -> &str {
        &self.group_id
    }

    /// The camera IDs (matching calibration keys).
    pub fn camera_ids(&self) -> &[String] {
        &self.camera_ids
    }
}

impl Drop for VideoGroup {
    fn drop(&mut self) {
        if self.state == VideoGroupState::Streaming {
            tracing::warn!(
                "[VideoGroup {}] dropped while streaming — shutting down",
                self.group_id
            );
            self.shutdown();
        }
    }
}

// ── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod pipeline_test;

#[cfg(test)]
mod tests {
    use super::*;
    use opencv::prelude::*;
    use std::path::Path;

    const TEST_BASE: &str =
        r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\synchronized_videos";

    fn test_video_paths() -> [String; 3] {
        [
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", TEST_BASE),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", TEST_BASE),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", TEST_BASE),
        ]
    }

    fn test_camera_ids() -> [String; 3] {
        ["Cam1".to_string(), "Cam2".to_string(), "Cam3".to_string()]
    }

    #[test]
    fn test_open_video_group() {
        let paths = test_video_paths();
        let cam_ids = test_camera_ids();

        // Skip if test data not available
        if !Path::new(&paths[0]).exists() {
            eprintln!("Skipping test — test videos not found");
            return;
        }

        let group = VideoGroup::open(&paths, &cam_ids);
        assert!(group.is_ok(), "Failed to open video group: {:?}", group.err());
        let group = group.unwrap();

        assert_eq!(group.frame_count(), 222);
        assert_eq!(group.n_cameras(), 3);
        assert_eq!(group.state, VideoGroupState::Created);
    }

    #[test]
    fn test_video_group_lifecycle() {
        let paths = test_video_paths();
        let cam_ids = test_camera_ids();

        if !Path::new(&paths[0]).exists() {
            eprintln!("Skipping test — test videos not found");
            return;
        }

        let mut group = VideoGroup::open(&paths, &cam_ids).expect("Failed to open");
        assert_eq!(group.state, VideoGroupState::Created);

        // Start with pacing=None (no pipeline attached), max_frames=5
        group.start(None, Some(5)).expect("Failed to start");
        assert_eq!(group.state, VideoGroupState::Streaming);

        // Give dispatcher time to push frames
        std::thread::sleep(std::time::Duration::from_millis(500));

        // Verify frames are flowing
        let raw = {
            group.latest_raw_frames.lock().unwrap().clone()
        };
        assert!(raw.is_some(), "Should have received frames");
        let raw = raw.unwrap();
        assert_eq!(raw.len(), 3, "Should have 3 camera frames");
        assert!(raw[0].frame_number >= 0, "Should have valid frame number");

        group.shutdown();
        assert_eq!(group.state, VideoGroupState::Stopped);
    }

    #[test]
    fn test_video_reader_metadata() {
        let paths = test_video_paths();
        if !Path::new(&paths[0]).exists() {
            eprintln!("Skipping test — test videos not found");
            return;
        }

        let reader = VideoReader::open(&paths[0]).expect("Failed to open");
        assert_eq!(reader.frame_count(), 222);
        assert!(reader.fps() > 0.0, "FPS should be positive");
        assert!(reader.width() > 0, "Width should be positive");
        assert!(reader.height() > 0, "Height should be positive");
    }

    #[test]
    fn test_video_reader_sequential_read() {
        let paths = test_video_paths();
        if !Path::new(&paths[0]).exists() {
            eprintln!("Skipping test — test videos not found");
            return;
        }

        let mut reader = VideoReader::open(&paths[0]).expect("Failed to open");

        for idx in 0..10 {
            let frame = reader.read_next();
            assert!(frame.is_some(), "Should have frame {}", idx);
            let frame = frame.unwrap();
            assert!(frame.is_ok(), "Frame {} error: {:?}", idx, frame.err());
            let frame = frame.unwrap();
            assert!(!frame.empty(), "Frame {} is empty", idx);
            assert_eq!(frame.typ(), opencv::core::CV_8UC3, "Frame {} should be BGR", idx);
        }

        assert_eq!(reader.current_frame_index(), 10);
    }
}
