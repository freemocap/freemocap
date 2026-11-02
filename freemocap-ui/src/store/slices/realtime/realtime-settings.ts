import type {CameraNodeConfig, RealtimePipelineConfig} from './realtime-types';

/** Keep application settings separate from Tracker's server-generated recipes.
 * Resolved responses contain both, but a subsequent Apply can select a different
 * detector, board or confidence. Tracker must resolve that recipe from the new
 * settings; replaying the previous recipe either conflicts or uses an old schema.
 */
export function realtimePipelineSettings(config: RealtimePipelineConfig): RealtimePipelineConfig {
    const cameraSettings: CameraNodeConfig & {
        skeleton_tracker_config?: unknown;
        charuco_tracker_config?: unknown;
    } = {...config.camera_node_config};
    delete cameraSettings.skeleton_tracker_config;
    delete cameraSettings.charuco_tracker_config;
    return {...config, camera_node_config: cameraSettings};
}

/** Project UI preferences into the observation-only DLC execution contract. */
export function realtimeExecutionSettings(config: RealtimePipelineConfig, dlcProvider: 'cpu' | 'cuda'): RealtimePipelineConfig {
    const settings = realtimePipelineSettings(config);
    if (settings.camera_node_config.detector_type !== 'dlc') return settings;
    return {
        ...settings,
        camera_node_config: {...settings.camera_node_config, charuco_tracking_enabled: false},
        skeleton_inference_node_config: {...settings.skeleton_inference_node_config, execution_provider: dlcProvider},
        aggregator_config: {...settings.aggregator_config, triangulation_enabled: false, skeleton_fitting_enabled: false,
            center_of_mass_enabled: false, calibration_toml_path: null, reference_transform: null},
    };
}

/** Server execution overrides must not erase the user's human-tracking preferences. */
export function acceptedRealtimeSettings(resolved: RealtimePipelineConfig, requested: RealtimePipelineConfig): RealtimePipelineConfig {
    const settings = realtimePipelineSettings(resolved);
    return requested.camera_node_config.detector_type === 'dlc' ? {
        ...settings,
        camera_node_config: {...settings.camera_node_config, charuco_tracking_enabled: requested.camera_node_config.charuco_tracking_enabled},
        aggregator_config: requested.aggregator_config,
        skeleton_inference_node_config: requested.skeleton_inference_node_config,
    } : settings;
}
