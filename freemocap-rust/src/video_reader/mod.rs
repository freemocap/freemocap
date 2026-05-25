//! Synchronized multi-video frame reader.
//!
//! `VideoGroup` opens N video files and reads them frame-by-frame in lockstep.
//! It uses sequential-only access (no seeking) to guarantee perfect frame sync.
//! Built on OpenCV `VideoCapture` for simplicity and reliability.
//!
//! ## Sync Guarantee
//!
//! `VideoCapture::read()` advances the internal frame counter by exactly 1
//! each call. As long as we never call `set(CAP_PROP_POS_FRAMES, n)`, the
//! N readers stay perfectly synchronized. Each call to `read_next()` returns
//! the same frame index from all videos.
//!
//! ## Usage
//!
//! ```ignore
//! let mut group = VideoGroup::open(&["cam1.mp4", "cam2.mp4", "cam3.mp4"])?;
//! while let Some(frames) = group.read_next()? {
//!     // frames[i] is the BGR image from camera i at the same frame number
//!     process_multiframe(&frames);
//! }
//! ```

use std::path::Path;

use opencv::core::Mat;
use opencv::prelude::*;
use opencv::videoio;

/// A synchronized group of video files.
///
/// All videos must have the same number of frames. Frames are read
/// sequentially — the internal cursor moves forward by one each `read_next()`
/// call and never seeks back.
pub struct VideoGroup {
    captures: Vec<videoio::VideoCapture>,
    frame_count: i32,
    current_frame: i32,
}

impl VideoGroup {
    /// Open a set of video files. Verifies they all have the same frame count.
    pub fn open(paths: &[impl AsRef<Path>]) -> Result<Self, String> {
        if paths.is_empty() {
            return Err("No video paths provided".into());
        }

        let mut captures = Vec::with_capacity(paths.len());
        let mut frame_count: Option<i32> = None;

        for path in paths {
            let path_ref: &Path = path.as_ref();
            let path_str = path_ref.to_string_lossy();

            let mut cap = videoio::VideoCapture::from_file(&path_str, videoio::CAP_FFMPEG)
                .map_err(|e| format!("Failed to open '{}': {:?}", path_str, e))?;

            if !cap.is_opened().unwrap_or(false) {
                return Err(format!("Video '{}' opened but is not ready", path_str));
            }

            // Verify frame count matches
            let fc = cap.get(videoio::CAP_PROP_FRAME_COUNT)
                .map_err(|e| format!("Failed to get frame count for '{}': {:?}", path_str, e))? as i32;

            match frame_count {
                None => frame_count = Some(fc),
                Some(expected) if fc != expected => {
                    return Err(format!(
                        "Frame count mismatch: '{}' has {} frames, expected {}",
                        path_str, fc, expected
                    ));
                }
                _ => {}
            }

            captures.push(cap);
        }

        let fc = frame_count.unwrap_or(0);
        Ok(VideoGroup {
            captures,
            frame_count: fc,
            current_frame: 0,
        })
    }

    /// Number of frames in each video.
    pub fn len(&self) -> i32 {
        self.frame_count
    }

    /// Whether all frames have been read.
    pub fn is_empty(&self) -> bool {
        self.current_frame >= self.frame_count
    }

    /// Current frame index (the one that will be returned by the next `read_next()`).
    pub fn current_frame_index(&self) -> i32 {
        self.current_frame
    }

    /// Read the next frame from all videos.
    ///
    /// Returns `Some(Vec<Mat>)` with one BGR image per video, or `None` if
    /// all frames have been exhausted. Each `Mat` is 8UC3 (BGR, u8 per channel).
    ///
    /// Frame index advances by 1 after this call. Never seeks — sequential
    /// access guarantees all captures stay at the same frame number.
    pub fn read_next(&mut self) -> Option<Result<Vec<Mat>, String>> {
        if self.current_frame >= self.frame_count {
            return None;
        }

        let mut frames = Vec::with_capacity(self.captures.len());
        for (i, cap) in self.captures.iter_mut().enumerate() {
            let mut frame = Mat::default();
            match cap.read(&mut frame) {
                Ok(true) => {
                    if frame.empty() {
                        return Some(Err(format!(
                            "Camera {} returned empty frame at index {}", i, self.current_frame
                        )));
                    }
                    frames.push(frame);
                }
                Ok(false) => {
                    return Some(Err(format!(
                        "Camera {} returned false (EOF?) at frame {}", i, self.current_frame
                    )));
                }
                Err(e) => {
                    return Some(Err(format!(
                        "Camera {} read error at frame {}: {:?}", i, self.current_frame, e
                    )));
                }
            }
        }

        self.current_frame += 1;
        Some(Ok(frames))
    }

    /// Reset to the beginning of all videos.
    ///
    /// Uses `set(CAP_PROP_POS_FRAMES, 0)` which triggers a seek. After
    /// calling this, the next `read_next()` returns frame 0.
    /// Only use this for multi-pass processing — the seek breaks the
    /// "never seek" guarantee, so frame sync must be re-verified.
    pub fn reset(&mut self) -> Result<(), String> {
        for (i, cap) in self.captures.iter_mut().enumerate() {
            cap.set(videoio::CAP_PROP_POS_FRAMES, 0.0)
                .map_err(|e| format!("Failed to seek camera {} to frame 0: {:?}", i, e))?;
        }
        self.current_frame = 0;
        Ok(())
    }

    /// Number of video streams.
    pub fn n_cameras(&self) -> usize {
        self.captures.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_open_video_group() {
        let base = r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\synchronized_videos";
        let videos = [
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", base),
        ];

        let group = VideoGroup::open(&videos);
        assert!(group.is_ok(), "Failed to open video group: {:?}", group.err());
        let group = group.unwrap();

        assert_eq!(group.len(), 222);
        assert_eq!(group.n_cameras(), 3);
    }

    #[test]
    fn test_read_frames_sequential() {
        let base = r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\synchronized_videos";
        let videos = [
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", base),
        ];

        let mut group = VideoGroup::open(&videos).expect("Failed to open videos");

        // Read first 10 frames
        for idx in 0..10 {
            let frames = group.read_next();
            assert!(frames.is_some(), "Should have frame {}", idx);
            let frames = frames.unwrap();
            assert!(frames.is_ok(), "Frame {} error: {:?}", idx, frames.err());
            let frames = frames.unwrap();
            assert_eq!(frames.len(), 3, "Should have 3 camera frames");
            for (i, frame) in frames.iter().enumerate() {
                assert!(!frame.empty(), "Camera {} frame {} is empty", i, idx);
                assert_eq!(frame.typ(), opencv::core::CV_8UC3, "Camera {} frame {} should be BGR", i, idx);
            }
        }

        assert_eq!(group.current_frame_index(), 10);
    }

    #[test]
    fn test_read_all_frames() {
        let base = r"C:\Users\jonma\freemocap_data\recordings\freemocap_test_data\synchronized_videos";
        let videos = [
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam1.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam2.mp4", base),
            format!("{}/sesh_2022-09-19_16_16_50_in_class_jsm_synced_Cam3.mp4", base),
        ];

        let mut group = VideoGroup::open(&videos).expect("Failed to open videos");
        let total = group.len();
        let mut count = 0;

        while let Some(result) = group.read_next() {
            assert!(result.is_ok(), "Frame {} error", count);
            count += 1;
        }

        assert_eq!(count, total, "Should have read all {} frames", total);
        assert!(group.is_empty());
    }
}
