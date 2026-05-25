use serde::{Deserialize, Serialize};

/// Top-level pipeline configuration. Deserialized from Python JSON
/// (Pydantic RealtimePipelineConfig.model_dump_json()).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    pub charuco_config: CharucoDetectorConfig,
    pub triangulation_enabled: bool,
    pub filter_config: FilterConfig,
    pub skeleton_enabled: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CharucoDetectorConfig {
    pub squares_x: u32,
    pub squares_y: u32,
    pub square_length_mm: f32,
    pub marker_length_ratio: f32,
    pub dictionary_enum: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FilterConfig {
    pub filter_enabled: bool,
    pub min_cutoff: f64,
    pub beta: f64,
    pub d_cutoff: f64,
    pub max_velocity_m_per_s: f64,
    pub max_reprojection_error_px: f64,
    pub max_rejected_streak: u32,
    pub skeleton_enabled: bool,
}

impl Default for PipelineConfig {
    fn default() -> Self {
        Self {
            charuco_config: CharucoDetectorConfig {
                squares_x: 5,
                squares_y: 7,
                square_length_mm: 30.0,
                marker_length_ratio: 0.75,
                dictionary_enum: 2, // DICT_4X4_250
            },
            triangulation_enabled: false,
            filter_config: FilterConfig {
                filter_enabled: true,
                min_cutoff: 1.0,
                beta: 0.01,
                d_cutoff: 1.0,
                max_velocity_m_per_s: 3.0,
                max_reprojection_error_px: 5.0,
                max_rejected_streak: 5,
                skeleton_enabled: false,
            },
            skeleton_enabled: false,
        }
    }
}
