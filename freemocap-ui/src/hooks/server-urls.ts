const DEFAULT_HOST = 'localhost';
const DEFAULT_PORT = 53117;

type PortChangeCallback = (port: number) => void;

class ServerUrls {
    private readonly host = DEFAULT_HOST;
    private port = DEFAULT_PORT;
    private portChangeListeners = new Set<PortChangeCallback>();

    /**
     * Update the port at runtime. Notifies all subscribers so components
     * can recreate connections with the correct URL.
     */
    setPort(port: number): void {
        if (port === this.port) return;
        console.log(`[ServerUrls] Port updated: ${this.port} → ${port}`);
        this.port = port;
        for (const listener of this.portChangeListeners) {
            listener(port);
        }
    }

    getPort(): number {
        return this.port;
    }

    /**
     * Subscribe to port changes. Returns an unsubscribe function.
     */
    onPortChange(callback: PortChangeCallback): () => void {
        this.portChangeListeners.add(callback);
        return () => {
            this.portChangeListeners.delete(callback);
        };
    }

    getHttpUrl(): string {
        return `http://${this.host}:${this.port}`;
    }

    getWebSocketUrl(): string {
        return `ws://${this.host}:${this.port}/websocket/connect`;
    }

    get endpoints() {
        const baseUrl = this.getHttpUrl();

        return {
            // Server management
            health: `${baseUrl}/health`,
            shutdown: `${baseUrl}/shutdown`,
            settings: `${baseUrl}/settings`,

            // Camera endpoints
            detectCameras: `${baseUrl}/skellycam/camera/detect`,
            camerasConnectOrUpdate: `${baseUrl}/skellycam/camera/group/apply`,
            closeAll: `${baseUrl}/skellycam/camera/group/close/all`,
            updateConfigs: `${baseUrl}/skellycam/camera/update`,
            pauseUnpauseCameras: `${baseUrl}/skellycam/camera/group/all/pause_unpause`,

            // Recording endpoints
            startRecording: `${baseUrl}/skellycam/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/skellycam/camera/group/all/record/stop`,

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

export const serverUrls = new ServerUrls();