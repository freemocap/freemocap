//! Pipeline data types — frame slots, channel messages, timestamps.

use skellycam::camera::types::FrameLifecycleTimestamps;

// ── Source-specific frame acquisition timestamps ─────────────────────────

/// Timestamps for frames read from video files.
///
/// These describe the video-file read + encode pipeline. Different semantics
/// from live camera capture — there's no "frame available" interrupt, no
/// gatherer synchronization. The fields describe what actually happens when
/// reading from disk.
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
    /// Live camera capture timestamps from skellycam's camera thread.
    Camera(FrameLifecycleTimestamps),
    /// Video file read + encode timestamps.
    Video(VideoFrameTimestamps),
}

// ── Per-camera detection stage timestamps ────────────────────────────────

/// Timestamps for per-camera detection stages.
///
/// These stages execute regardless of whether the frame came from a live
/// camera or a video file — JPEG decode, charuco detection, channel send.
/// Only the `source` field varies by frame origin.
#[derive(Debug, Clone)]
pub struct DetectionTimestamps {
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

// ── Pipeline-wide multiframe timestamps ──────────────────────────────────

/// Per-multiframe timestamps added by freemocap pipeline stages
/// (distributor + aggregator). All ns since T=0.
#[derive(Debug, Clone, Default)]
pub struct PipelineTimestamps {
    /// When distributor wrote the shared slot.
    pub distributor_slot_write_ns: i64,
    /// When distributor released cameras from the barrier.
    pub distributor_barrier_release_ns: i64,
    /// When aggregator started collecting camera outputs.
    pub aggregator_collection_start_ns: i64,
    /// When all camera outputs were received.
    pub aggregator_all_received_ns: i64,
    /// After charuco triangulation.
    pub aggregator_post_triangulation_ns: i64,
    /// After filter chain (velocity gate + One Euro).
    pub aggregator_post_filter_ns: i64,
    /// When output was published to the shared output slot.
    pub aggregator_output_published_ns: i64,
}

// ── Channel message types ────────────────────────────────────────────────

/// Output from a single camera node after detection.
#[derive(Debug, Clone)]
pub struct CameraNodeOutput {
    pub camera_id: String,
    pub frame_number: i64,
    /// Charuco detection result. Boxed because CharucoObservation is large
    /// (contains Vecs of corners, IDs, etc.).
    pub charuco_observation:
        Option<Box<skellytracker::trackers::charuco::observation::CharucoObservation>>,
    /// Per-camera detection-stage timestamps.
    pub timestamps: DetectionTimestamps,
}

/// Aggregated output for one multiframe cycle. Stored in a shared slot
/// for the Python websocket relay to poll.
#[derive(Debug, Clone)]
pub struct AggregatorOutput {
    pub frame_number: i64,
    /// Per-camera detection outputs (for charuco overlay data).
    pub camera_outputs: Vec<CameraNodeOutput>,
    /// Raw triangulated keypoints: point_name → [x, y, z].
    pub keypoints_raw: std::collections::HashMap<String, [f64; 3]>,
    /// Filtered keypoints after velocity gate + One Euro filter.
    pub keypoints_filtered: std::collections::HashMap<String, [f64; 3]>,
    /// The pre-encoded frontend payload captured by the distributor.
    pub frontend_payload_bytes: Vec<u8>,
    /// Multiframe timestamp from skellycam's payload.
    pub timestamp_ns: f64,
    /// True camera FPS from skellycam's framerate tracker.
    pub camera_fps: f64,
    /// Per-multiframe timestamps through distributor + aggregator stages.
    pub pipeline_timestamps: PipelineTimestamps,
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
    /// Distributor timestamps for this multiframe.
    pub distributor_timestamps: PipelineTimestamps,
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
