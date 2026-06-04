export interface DefaultUrlConfig {
    host: string;
    port: number;
}

// Default URL configuration
const defaultUrlConfig: DefaultUrlConfig = {
    host: 'localhost',
    port: 8006,
};


// Get the base HTTP URL
const getBaseHttpUrl = () => {
    const {host, port} = defaultUrlConfig;
    return `http://${host}:${port}`;
};

// Get a specific API URL
const getApiUrl = (path: string) => {
    return `${getBaseHttpUrl()}${path}`;
};

// Get WebSocket URL
const getWebSocketUrl = () => {
    const {host, port} = defaultUrlConfig;
    return `ws://${host}:${port}/skellycam/websocket/connect`;
};

// Get all HTTP endpoint URLs
const getHttpEndpointUrls = () => {
    return {
        health: getApiUrl('/health'),
        shutdown: getApiUrl('/shutdown'),
        detectCameras: getApiUrl('/skellycam/camera/detect'),
        createGroup: getApiUrl('/skellycam/camera/group/apply'),
        closeAll: getApiUrl('/skellycam/camera/group/close/all'),
        updateConfigs: getApiUrl('/skellycam/camera/update'),
        startRecording: getApiUrl('/skellycam/camera/group/all/record/start'),
        stopRecording: getApiUrl('/skellycam/camera/group/all/record/stop'),
        pauseUnpauseCameras: getApiUrl('/skellycam/camera/group/all/pause_unpause'),
    };
};

export const useAppUrls = {
    getBaseHttpUrl,
    getApiUrl,
    getWebSocketUrl,
    getHttpEndpointUrls,
};
