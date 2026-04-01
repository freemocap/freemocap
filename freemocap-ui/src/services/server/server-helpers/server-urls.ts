export const DEFAULT_HOST = 'localhost';
export const DEFAULT_PORT = 53117;
export const WS_PATH = '/freemocap/websocket/connect';

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
            detectCameras: `${baseUrl}/freemocap/camera/detect`,
            camerasConnectOrUpdate: `${baseUrl}/freemocap/camera/group/apply`,
            closeAll: `${baseUrl}/freemocap/camera/group/close/all`,
            updateConfigs: `${baseUrl}/freemocap/camera/update`,
            pauseUnpauseCameras: `${baseUrl}/freemocap/camera/group/all/pause_unpause`,
            detectMicrophones: `${baseUrl}/freemocap/camera/microphone/detect`,

            // Recording endpoints
            startRecording: `${baseUrl}/freemocap/camera/group/all/record/start`,
            stopRecording: `${baseUrl}/freemocap/camera/group/all/record/stop`,

            // Playback endpoints
            playbackRecordings: `${baseUrl}/freemocap/playback/recordings`,
            playbackLoad: `${baseUrl}/freemocap/playback/load`,
            playbackVideos: `${baseUrl}/freemocap/playback/videos`,
            playbackVideoStream: (videoId: string) => `${baseUrl}/freemocap/playback/video/${videoId}`,
            playbackTimestamps: (videoId: string) => `${baseUrl}/freemocap/playback/timestamps/${videoId}`,
            playbackAllTimestamps: `${baseUrl}/freemocap/playback/timestamps`,

            // WebSocket
            websocket: this.getWebSocketUrl(),
        };
    }
}

// Export singleton instance
export const serverUrls = new ServerUrls();
