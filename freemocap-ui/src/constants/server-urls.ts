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
            pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause_unpause`,
            detectMicrophones: `${baseUrl}/skellycam/camera/microphone/detect`,

            // Playback endpoints
            playbackRecordings: `${baseUrl}/freemocap/playback/recordings`,
            playbackVideos: (recordingId: string) =>
                `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/videos`,
            playbackVideoStream: (recordingId: string, videoId: string) =>
                `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/videos/${encodeURIComponent(videoId)}`,
            playbackAllTimestamps: (recordingId: string) =>
                `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/timestamps`,
            playbackVideoTimestamps: (recordingId: string, videoId: string) =>
                `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/videos/${encodeURIComponent(videoId)}/timestamps`,
            playbackRecordingStatus: (recordingId: string) =>
                `${baseUrl}/freemocap/playback/${encodeURIComponent(recordingId)}/status`,

            // Recording endpoints
            startRecording: `${baseUrl}/freemocap/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/freemocap/camera/group/all/record/stop`,

            // Realtime pipeline endpoints
            realtimeConnectOrUpdate: `${baseUrl}/freemocap/realtime/apply`,
            realtimeClose: `${baseUrl}/freemocap/realtime/all/close`,

            // Calibration endpoints
            calibrationStartRecording: `${baseUrl}/freemocap/calibration/recording/start`,
            calibrationStopRecording: `${baseUrl}/freemocap/calibration/recording/stop`,
            calibrateRecording: `${baseUrl}/freemocap/calibration/recording/calibrate`,

            // Mocap endpoints
            mocapStartRecording: `${baseUrl}/freemocap/mocap/recording/start`,
            mocapStopRecording: `${baseUrl}/freemocap/mocap/recording/stop`,
            processMocapRecording: `${baseUrl}/freemocap/mocap/recording/process`,

            // Blender endpoints
            blenderDetect: `${baseUrl}/freemocap/blender/detect`,
            blenderExport: `${baseUrl}/freemocap/blender/export`,
            blenderOpen: `${baseUrl}/freemocap/blender/open`,

            // WebSocket
            websocket: this.getWebSocketUrl(),
        };
    }
}

// Export singleton instance
export const serverUrls = new ServerUrls();
