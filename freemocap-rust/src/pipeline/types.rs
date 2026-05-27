//! Pipeline data types — frame slots, channel messages, composable timestamps.
//!
//! ## Timestamp design
//! Every loop gets its own `Timestamps` struct with named stage-boundary fields
//! (all `i64` nanoseconds since T=0). Durations are computed as `end − start`.
//! Composite loops compose their children's timestamp structs as fields.

use std::collections::HashMap;
use skellycam::camera::types::FrameLifecycleTimestamps;

// ── Source-specific frame acquisition timestamps ─────────────────────────

/// Timestamps for frames read from video files.
#[derive(Debug, Clone)]
pub struct VideoFrameTimestamps {
    /// When the dispatcher began reading this multiframe from disk.
    pub video_read_start_ns: i64,
    /// After all `VideoCapture::read()` calls returned for this multiframe.
    pub video_read_done_ns: i64,
    /// After BGR → JPEG encoding completed for all cameras.
    pub video_encode_done_ns: i64,
    /// After `RawFrame` + `FrontendPayload` structs were built.
    pub video_payload_built_ns: i64,
    /// Immediately after writing to FrameSlots (last timestamp in video source).
    pub video_slots_written_ns: i64,
}

/// Frame acquisition timestamps — varies by source type.
#[derive(Debug, Clone)]
pub enum SourceFrameTimestamps {
    Camera(FrameLifecycleTimestamps),
    Video(VideoFrameTimestamps),
}

// ── Per-loop timestamp structs ───────────────────────────────────────────

/// Timestamps for the distributor thread's main loop.
///
/// One per pipeline cycle. The distributor polls for frames, writes the
/// shared slot, and releases camera nodes via the barrier.
#[derive(Debug, Clone, Default)]
pub struct DistributorTimestamps {
    /// Start of the productive portion of this cycle (after command checking).
    pub cycle_start_ns: i64,
    /// After reading FrameSlots (or receiving from mpsc channel) and writing
    /// the `DistributorSlot`.
    pub slot_write_done_ns: i64,
    /// Immediately before calling `barrier.wait()`.
    pub barrier_release_ns: i64,
    /// After `barrier.wait()` returned.
    pub barrier_return_ns: i64,
}

impl DistributorTimestamps {
    /// Time spent polling for frames + writing the slot.
    pub fn slot_work_ns(&self) -> i64 { self.slot_write_done_ns - self.cycle_start_ns }
    /// Time spent waiting at the BreakableBarrier.
    pub fn barrier_wait_ns(&self) -> i64 { self.barrier_return_ns - self.barrier_release_ns }
    /// Full cycle time.
    pub fn total_ns(&self) -> i64 { self.barrier_return_ns - self.cycle_start_ns }
}

/// Timestamps for a single camera node's detection loop.
///
/// One per camera per pipeline cycle. Camera nodes run in parallel —
/// each measures its own stages independently.
#[derive(Debug, Clone)]
pub struct CameraNodeTimestamps {
    /// Frame acquisition timestamps (camera- or video-specific).
    pub source: SourceFrameTimestamps,
    /// When this camera node read its frame from the shared distributor slot.
    pub dequeue_ns: i64,
    /// After JPEG → BGR decode.
    pub post_jpeg_decode_ns: i64,
    /// After charuco detection.
    pub post_detection_ns: i64,
    /// Before sending to aggregator channel.
    pub pre_send_ns: i64,
}

impl CameraNodeTimestamps {
    pub fn jpeg_decode_ns(&self) -> i64 { self.post_jpeg_decode_ns - self.dequeue_ns }
    pub fn charuco_detect_ns(&self) -> i64 { self.post_detection_ns - self.post_jpeg_decode_ns }
    pub fn total_ns(&self) -> i64 { self.pre_send_ns - self.dequeue_ns }
}

/// Timestamps for the aggregator thread's main loop.
///
/// One per pipeline cycle. The aggregator collects camera outputs,
/// triangulates, filters, and publishes results.
#[derive(Debug, Clone)]
pub struct AggregatorTimestamps {
    /// When the aggregator started collecting camera outputs.
    pub collection_start_ns: i64,
    /// When all camera outputs were received.
    pub all_received_ns: i64,
    /// After charuco triangulation + outlier rejection.
    pub post_triangulation_ns: i64,
    /// After velocity gate + One Euro filter.
    pub post_filtering_ns: i64,
    /// When output was published to the shared output slot.
    pub output_published_ns: i64,
}

impl AggregatorTimestamps {
    /// Time spent waiting for all cameras to send (includes blocking recv).
    pub fn collection_ns(&self) -> i64 { self.all_received_ns - self.collection_start_ns }
    /// Triangulation computation time.
    pub fn triangulation_ns(&self) -> i64 { self.post_triangulation_ns - self.all_received_ns }
    /// Velocity gate + One Euro filter time.
    pub fn filtering_ns(&self) -> i64 { self.post_filtering_ns - self.post_triangulation_ns }
    /// Time to publish output.
    pub fn output_publish_ns(&self) -> i64 { self.output_published_ns - self.post_filtering_ns }
    /// Full aggregator cycle time.
    pub fn total_ns(&self) -> i64 { self.output_published_ns - self.collection_start_ns }
}

/// Composite timestamps for one full pipeline cycle.
///
/// Composes the distributor's, each camera node's, and the aggregator's
/// per-loop timestamp structs. Keyed by `camera_id` for per-camera lookups.
#[derive(Debug, Clone)]
pub struct PipelineCycleTimestamps {
    pub distributor: DistributorTimestamps,
    /// Per-camera detection timestamps, keyed by camera_id.
    pub cameras: HashMap<String, CameraNodeTimestamps>,
    pub aggregator: AggregatorTimestamps,
}

// ── Channel message types ────────────────────────────────────────────────

/// Output from a single camera node after detection.
#[derive(Debug, Clone)]
pub struct CameraNodeOutput {
    pub camera_id: String,
    pub frame_number: i64,
    /// Charuco detection result. Boxed because CharucoObservation is large.
    pub charuco_observation:
        Option<Box<skellytracker::trackers::charuco::observation::CharucoObservation>>,
    /// Per-camera detection-stage timestamps.
    pub timestamps: CameraNodeTimestamps,
}

/// Aggregated output for one multiframe cycle. Stored in a shared slot
/// for the Python websocket relay to poll.
#[derive(Debug, Clone)]
pub struct AggregatorOutput {
    pub frame_number: i64,
    /// Per-camera detection outputs (for charuco overlay data).
    pub camera_outputs: Vec<CameraNodeOutput>,
    /// Raw triangulated keypoints: point_name → [x, y, z].
    pub keypoints_raw: HashMap<String, [f64; 3]>,
    /// Filtered keypoints after velocity gate + One Euro filter.
    pub keypoints_filtered: HashMap<String, [f64; 3]>,
    /// The pre-encoded frontend payload captured by the distributor.
    pub frontend_payload_bytes: Vec<u8>,
    /// Multiframe timestamp from skellycam's payload.
    pub timestamp_ns: f64,
    /// True camera FPS from skellycam's framerate tracker.
    pub camera_fps: f64,
    /// Composite pipeline cycle timestamps.
    pub cycle_timestamps: PipelineCycleTimestamps,
}

// ── Distributor slot ─────────────────────────────────────────────────────

/// Data written by the distributor and read by all camera nodes.
/// Protected by `Arc<RwLock<DistributorSlot>>` with a BreakableBarrier
/// ensuring all cameras read the same version.
#[derive(Debug, Clone)]
pub struct DistributorSlot {
    pub frame_number: i64,
    /// Per-camera data: (camera_id, jpeg_bytes, source timestamps).
    pub per_camera_data: Vec<PerCameraFrameData>,
    /// Pre-encoded frontend payload — bundled at capture time.
    pub frontend_payload_bytes: Vec<u8>,
    pub timestamp_ns: f64,
    pub camera_fps: f64,
    /// Distributor timestamps for this cycle.
    pub distributor_timestamps: DistributorTimestamps,
}

/// Complete per-camera frame data for one multiframe cycle.
/// Built by the distributor from the source's FrameSlots.
#[derive(Debug, Clone)]
pub struct PerCameraFrameData {
    pub camera_id: String,
    pub jpeg_bytes: Vec<u8>,
    /// Frame acquisition timestamps — Camera variant for live capture,
    /// Video variant for file-based sources.
    pub source_timestamps: SourceFrameTimestamps,
}
