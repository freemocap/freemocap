export interface ExportChannel {
    sensor_group: string;
    source: string;
    reference_frame: string | null;
    channel: string;
    static: boolean;
}
export type ExportFormat = 'wide_csv' | 'npy' | 'npz' | 'notebook';
export type ExportChannelKind = 'LANDMARKS_3D' | 'KEYPOINTS_3D' | 'RAW_KEYPOINTS_3D' | 'OVERLAY_2D' | 'SEGMENT_POSES';
export const channelKey = (c: ExportChannel) => JSON.stringify([c.sensor_group, c.source, c.reference_frame, c.channel, c.static]);
