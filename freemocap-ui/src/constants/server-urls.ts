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

            // Camera endpoints
            detectCameras: `${baseUrl}/skellycam/camera/detect`,
            camerasConnectOrUpdate: `${baseUrl}/skellycam/camera/group/apply`,
            closeAll: `${baseUrl}/skellycam/camera/group/close/all`,
            updateConfigs: `${baseUrl}/skellycam/camera/update`,
            pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause_unpause`,
            detectMicrophones: `${baseUrl}/skellycam/camera/microphone/detect`,

            // Recording endpoints
            startRecording: `${baseUrl}/skellycam/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/skellycam/camera/group/all/record/stop`,

            // Playback endpoints
            playbackRecordings: `${baseUrl}/skellycam/playback/recordings`,
            playbackLoad: `${baseUrl}/skellycam/playback/load`,
            playbackVideos: `${baseUrl}/skellycam/playback/videos`,
            playbackVideoStream: (videoId: string) => `${baseUrl}/skellycam/playback/video/${videoId}`,
            playbackTimestamps: (videoId: string) => `${baseUrl}/skellycam/playback/timestamps/${videoId}`,
            playbackAllTimestamps: `${baseUrl}/skellycam/playback/timestamps`,

            // Pipeline endpoints
            pipelineConnectOrUpdate: `${baseUrl}/freemocap/pipeline/connect`,
            pipelineClose: `${baseUrl}/freemocap/pipeline/all/close`,
            pipelinePauseUnpause: `${baseUrl}/freemocap/pipeline/all/pause_unpause`,
            pipelineRecordStart: `${baseUrl}/freemocap/pipeline/all/record/start`,
            pipelineRecordStop: `${baseUrl}/freemocap/pipeline/all/record/stop`,

            // Calibration endpoints
            calibrationStartRecording: `${baseUrl}/freemocap/calibration/recording/start`,
            calibrationStopRecording: `${baseUrl}/freemocap/calibration/recording/stop`,
            calibrateRecording: `${baseUrl}/freemocap/calibration/recording/calibrate`,
            updateCalibrationConfig: `${baseUrl}/freemocap/calibration/config/update/all`,

            // Mocap endpoints
            mocapStartRecording: `${baseUrl}/freemocap/mocap/recording/start`,
            mocapStopRecording: `${baseUrl}/freemocap/mocap/recording/stop`,
            processMocapRecording: `${baseUrl}/freemocap/mocap/recording/process`,
            updateMocapConfig: `${baseUrl}/freemocap/mocap/config/update/all`,

            // WebSocket
            websocket: this.getWebSocketUrl(),
        };
    }
}

// Export singleton instance
export const serverUrls = new ServerUrls();
