/// Per-camera timestamps extending skellycam's `FrameLifecycleTimestamps`
/// through the freemocap camera node stage.
#[derive(Debug, Clone)]
pub struct CameraPipelineTimestamps {
    /// skellycam's per-camera timestamps carried through from RawFrame:
    /// loop_start, frame_available, post_jpeg_extract, pre_send, gatherer_received.
    pub skellycam: skellycam::camera::types::FrameLifecycleTimestamps,
    /// When this camera node read its frame from the shared distributor slot.
    pub camera_dequeue_ns: i64,
    /// After JPEG → BGR decode.
    pub camera_post_jpeg_decode_ns: i64,
    /// After charuco detection.
    pub camera_post_detection_ns: i64,
    /// Before sending to aggregator channel.
    pub camera_pre_send_ns: i64,
}

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

/// Output from a single camera node after detection.
#[derive(Debug, Clone)]
pub struct CameraNodeOutput {
    pub camera_id: String,
    pub frame_number: i64,
    /// Charuco detection result. Boxed because CharucoObservation is large
    /// (contains Vecs of corners, IDs, etc.).
    pub charuco_observation:
        Option<Box<skellytracker::trackers::charuco::observation::CharucoObservation>>,
    /// Per-camera timestamps through skellycam + freemocap stages.
    pub timestamps: CameraPipelineTimestamps,
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

/// Data written by the distributor and read by all camera nodes.
/// Protected by `Arc<RwLock<DistributorSlot>>` with a BreakableBarrier
/// ensuring all cameras read the same version.
#[derive(Debug, Clone)]
pub struct DistributorSlot {
    pub frame_number: i64,
    /// Per-camera data: (camera_id, jpeg_bytes, skellycam timestamps).
    pub per_camera_data: Vec<PerCameraFrameData>,
    /// Pre-encoded frontend payload — bundled at capture time.
    pub frontend_payload_bytes: Vec<u8>,
    pub timestamp_ns: f64,
    pub camera_fps: f64,
    /// Distributor timestamps for this multiframe.
    pub distributor_timestamps: PipelineTimestamps,
}

/// Complete per-camera frame data for one multiframe cycle.
/// Built by the distributor from skellycam's RawFrame.
#[derive(Debug, Clone)]
pub struct PerCameraFrameData {
    pub camera_id: String,
    pub jpeg_bytes: Vec<u8>,
    /// skellycam FrameLifecycleTimestamps: loop_start, frame_available,
    /// post_jpeg_extract, pre_send, gatherer_received (all ns since T=0).
    pub skellycam_timestamps: skellycam::camera::types::FrameLifecycleTimestamps,
}

