//! Single video file reader wrapping OpenCV `VideoCapture`.
//!
//! Provides sequential frame access with metadata (FPS, dimensions, frame count).
//! Uses sequential-only access — no seeking during normal read, which guarantees
//! frame sync when multiple readers are driven in lockstep.

use std::path::Path;

use opencv::core::Mat;
use opencv::prelude::*;
use opencv::videoio;

pub struct VideoReader {
    capture: videoio::VideoCapture,
    fps: f64,
    width: u32,
    height: u32,
    frame_count: i32,
    current_frame: i32,
}

impl VideoReader {
    /// Open a single video file and read its metadata.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, String> {
        let path_ref = path.as_ref();
        let path_str = path_ref.to_string_lossy();

        let capture = videoio::VideoCapture::from_file(&path_str, videoio::CAP_ANY)
            .map_err(|e| format!("Failed to open '{}': {:?}", path_str, e))?;

        if !capture.is_opened().unwrap_or(false) {
            return Err(format!("Video '{}' opened but is not ready", path_str));
        }

        let fps = capture
            .get(videoio::CAP_PROP_FPS)
            .map_err(|e| format!("Failed to get FPS for '{}': {:?}", path_str, e))?;

        let width = capture
            .get(videoio::CAP_PROP_FRAME_WIDTH)
            .map_err(|e| format!("Failed to get width for '{}': {:?}", path_str, e))? as u32;

        let height = capture
            .get(videoio::CAP_PROP_FRAME_HEIGHT)
            .map_err(|e| format!("Failed to get height for '{}': {:?}", path_str, e))? as u32;

        let frame_count = capture
            .get(videoio::CAP_PROP_FRAME_COUNT)
            .map_err(|e| format!("Failed to get frame count for '{}': {:?}", path_str, e))? as i32;

        Ok(Self {
            capture,
            fps,
            width,
            height,
            frame_count,
            current_frame: 0,
        })
    }

    pub fn fps(&self) -> f64 {
        self.fps
    }

    pub fn width(&self) -> u32 {
        self.width
    }

    pub fn height(&self) -> u32 {
        self.height
    }

    pub fn frame_count(&self) -> i32 {
        self.frame_count
    }

    pub fn current_frame_index(&self) -> i32 {
        self.current_frame
    }

    /// Read the next frame. Returns `None` if all frames have been exhausted.
    ///
    /// The returned `Mat` is 8UC3 (BGR, u8 per channel). Sequential access
    /// guarantees the internal cursor stays at the correct position — never
    /// seeks, so frame sync across multiple readers is maintained.
    pub fn read_next(&mut self) -> Option<Result<Mat, String>> {
        if self.current_frame >= self.frame_count {
            return None;
        }

        let mut frame = Mat::default();
        match self.capture.read(&mut frame) {
            Ok(true) => {
                if frame.empty() {
                    return Some(Err(format!(
                        "Empty frame at index {}", self.current_frame
                    )));
                }
                self.current_frame += 1;
                Some(Ok(frame))
            }
            Ok(false) => Some(Err(format!(
                "EOF at frame {}", self.current_frame
            ))),
            Err(e) => Some(Err(format!(
                "Read error at frame {}: {:?}", self.current_frame, e
            ))),
        }
    }

    /// Reset to the beginning of the video.
    ///
    /// Uses `set(CAP_PROP_POS_FRAMES, 0)` which triggers a seek. After calling
    /// this, the next `read_next()` returns frame 0. Only use for multi-pass
    /// processing.
    pub fn reset(&mut self) -> Result<(), String> {
        self.capture
            .set(videoio::CAP_PROP_POS_FRAMES, 0.0)
            .map_err(|e| format!("Failed to seek to frame 0: {:?}", e))?;
        self.current_frame = 0;
        Ok(())
    }
}
