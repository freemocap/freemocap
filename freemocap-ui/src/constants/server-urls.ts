import {recordingQuery} from '../services/recording/recording-location';

export const DEFAULT_HOST = 'localhost';
export const DEFAULT_PORT = 53117;
export const WS_PATH = '/websocket/connect';

class ServerUrls {
    private host: string = DEFAULT_HOST;
    private port: number = DEFAULT_PORT;

    getHost(): string {
        return this.host;
    }

    getPort(): number {
        return this.port;
    }

    setHost(host: string): void {
        this.host = host;
    }

    setPort(port: number): void {
        this.port = port;
    }

    /**
     * Get HTTP base URL
     */
    getHttpUrl(): string {
        return `http://${this.host}:${this.port}`;
    }

    /**
     * Get WebSocket base URL
     */
    getWebSocketUrl(): string {
        return `ws://${this.host}:${this.port}${WS_PATH}`;
    }

    recordingResource(recordingId: string, resource = '', parent?: string | null,
                      parameters: Record<string, string> = {}): string {
        return `${this.getHttpUrl()}/freemocap/recordings/${encodeURIComponent(recordingId)}${resource}${recordingQuery(parent, parameters)}`;
    }

    get endpoints() {
        const baseUrl = this.getHttpUrl();

        return {
            // Server management
            health: `${baseUrl}/health`,
            shutdown: `${baseUrl}/shutdown`,

            // Camera endpoints (SkellyCam)
            detectCameras: `${baseUrl}/skellycam/camera/detect`,
            camerasConnectOrUpdate: `${baseUrl}/skellycam/camera/group/apply`,
            closeAll: `${baseUrl}/skellycam/camera/group/close/all`,
            updateConfigs: `${baseUrl}/skellycam/camera/update`,
            pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause`,
            detectMicrophones: `${baseUrl}/skellycam/camera/microphone/detect`,
            // Recording endpoints
            startRecording: `${baseUrl}/skellycam/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/skellycam/camera/group/all/record/stop`,

            // Playback endpoints
            playbackRecordings: `${baseUrl}/freemocap/recordings`,
            playbackVideos: (recordingId: string) =>
                this.recordingResource(recordingId, '/videos'),
            playbackVideoStream: (recordingId: string, videoId: string) =>
                this.recordingResource(recordingId, `/videos/${encodeURIComponent(videoId)}`),
            playbackRecordingStatus: (recordingId: string) =>
                this.recordingResource(recordingId, '/status'),
            playbackBundle: (recordingId: string) =>
                this.recordingResource(recordingId, '/playback/bundle'),


            // Realtime pipeline endpoints
            realtimeConnectOrUpdate: `${baseUrl}/freemocap/realtime/apply`,
            realtimeClose: `${baseUrl}/freemocap/realtime/pipelines`,
            resetSkeletonFitter: `${baseUrl}/freemocap/realtime/reset-skeleton-fitter`,

            // Calibration endpoints
            calibrationStartRecording: `${baseUrl}/freemocap/capture/calibration/start`,
            calibrationMostRecent: `${baseUrl}/freemocap/calibration/most-recent`,
            calibrationContent: `${baseUrl}/freemocap/calibration/content`,
            calibrationTransform: `${baseUrl}/freemocap/calibration/transform`,
            calibrationStopRecording: `${baseUrl}/freemocap/capture/calibration/stop`,

            // Mocap endpoints
            mocapStartRecording: `${baseUrl}/freemocap/capture/mocap/start`,
            mocapStopRecording: `${baseUrl}/freemocap/capture/mocap/stop`,
            importVideos: `${baseUrl}/freemocap/recording-import`,
            checkVideoSync: `${baseUrl}/freemocap/recording-import/check-sync`,
            synchronizeVideos: `${baseUrl}/freemocap/recording-import/synchronize`,
            synchronizeVideosResult: (jobId: string) =>
                `${baseUrl}/freemocap/tasks/${encodeURIComponent(`sync:${jobId}`)}`,

            // Posthoc pipeline control

            // Telemetry
            trackTelemetry: `${baseUrl}/freemocap/telemetry/track`,

            // Blender endpoints
            blenderDetect: `${baseUrl}/freemocap/blender/detect`,
            blenderExport: `${baseUrl}/freemocap/blender/export`,
            blenderOpen: `${baseUrl}/freemocap/blender/open`,

            // Ffmpeg endpoints
            ffmpegDetect: `${baseUrl}/freemocap/ffmpeg/detect`,

            // WebSocket
            websocket: this.getWebSocketUrl(),
        };
    }
}

// Export singleton instance
export const serverUrls = new ServerUrls();
