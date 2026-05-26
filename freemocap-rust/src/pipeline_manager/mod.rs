use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;

use uuid::Uuid;

use crate::pipeline::config::PipelineConfig;
use crate::pipeline::types::AggregatorOutput;

use skellycam::camera_group::FrameSlots;

/// Placeholder type for future posthoc pipeline support.
pub struct PosthocPipeline;

/// A running real-time pipeline attached to a camera group.
pub struct RealtimePipeline {
    pub pipeline_id: String,
    pub camera_ids: Vec<String>,
    pub config: PipelineConfig,
    /// Frame slots shared with the CameraGroup's dispatcher thread.
    /// Stored here so start() can pass them to the distributor thread.
    #[allow(dead_code)]
    pub frame_slots: FrameSlots,
    /// Aggregator output slot — polled for the latest processed frame.
    pub output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    pub shutdown_flag: Arc<AtomicBool>,
    pub handles: Vec<JoinHandle<()>>,
}

/// Manages the lifecycle of real-time and posthoc pipelines.
///
/// Each pipeline is keyed by a unique pipeline ID (6-char UUID prefix).
/// A pipeline optionally attaches to a `CameraGroup` via `FrameSlots`
/// (shared `Arc` references to the camera group's frame data slots).
/// Camera groups exist independently; pipelines are optional additions.
pub struct PipelineManager {
    realtime: HashMap<String, RealtimePipeline>,
    posthoc: HashMap<String, PosthocPipeline>,
}

impl PipelineManager {
    pub fn new() -> Self {
        Self {
            realtime: HashMap::new(),
            posthoc: HashMap::new(),
        }
    }

    // ── Realtime pipeline CRUD ────────────────────────────────────────────

    /// Create a new real-time pipeline attached to the given frame slots.
    /// Returns the pipeline ID.
    pub fn create_realtime_pipeline(
        &mut self,
        frame_slots: FrameSlots,
        config: PipelineConfig,
        camera_ids: Vec<String>,
    ) -> String {
        let pipeline_id = Uuid::new_v4().to_string()[..6].to_string();

        let output_slot = Arc::new(Mutex::new(None));
        let shutdown_flag = Arc::new(AtomicBool::new(false));

        // Thread spawning: in the PyO3 path, PyPipeline.start() handles this.
        // In the HTTP/binary path, a start() method on RealtimePipeline will
        // spawn threads using the stored frame_slots (next milestone).
        let pipeline = RealtimePipeline {
            pipeline_id: pipeline_id.clone(),
            camera_ids,
            config,
            frame_slots,
            output_slot,
            shutdown_flag,
            handles: Vec::new(),
        };

        self.realtime.insert(pipeline_id.clone(), pipeline);
        pipeline_id
    }

    pub fn get_realtime_pipeline(&self, pipeline_id: &str) -> Option<&RealtimePipeline> {
        self.realtime.get(pipeline_id)
    }

    pub fn get_realtime_pipeline_mut(
        &mut self,
        pipeline_id: &str,
    ) -> Option<&mut RealtimePipeline> {
        self.realtime.get_mut(pipeline_id)
    }

    /// Shut down and remove a real-time pipeline. Returns true if it existed.
    pub fn remove_realtime_pipeline(&mut self, pipeline_id: &str) -> bool {
        if let Some(mut pipeline) = self.realtime.remove(pipeline_id) {
            pipeline.shutdown_flag.store(true, Ordering::SeqCst);
            for handle in pipeline.handles.drain(..) {
                let _ = handle.join();
            }
            true
        } else {
            false
        }
    }

    pub fn update_realtime_pipeline_config(
        &mut self,
        pipeline_id: &str,
        config: PipelineConfig,
    ) -> Option<()> {
        self.realtime
            .get(pipeline_id)
            .map(|p| {
                // Config update via command channel will be wired when thread
                // spawning is implemented.
                let _ = &config;
            })
    }

    // ── Posthoc pipeline CRUD (deferred) ──────────────────────────────────

    pub fn create_posthoc_pipeline(&mut self) -> String {
        unimplemented!("posthoc pipeline support not yet implemented")
    }

    // ── Global ────────────────────────────────────────────────────────────

    pub fn shutdown_all(&mut self) {
        for (_, pipeline) in self.realtime.drain() {
            pipeline.shutdown_flag.store(true, Ordering::SeqCst);
            for handle in pipeline.handles {
                let _ = handle.join();
            }
        }
        self.posthoc.clear();
    }

    pub fn list_realtime_pipelines(&self) -> Vec<String> {
        self.realtime.keys().cloned().collect()
    }

    pub fn realtime_pipeline_count(&self) -> usize {
        self.realtime.len()
    }
}

impl Drop for PipelineManager {
    fn drop(&mut self) {
        self.shutdown_all();
    }
}
