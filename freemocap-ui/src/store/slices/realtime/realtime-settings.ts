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
