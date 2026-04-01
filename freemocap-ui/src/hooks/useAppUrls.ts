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
    return `ws://${host}:${port}/freemocap/websocket/connect`;
};

// Get all HTTP endpoint URLs
const getHttpEndpointUrls = () => {
    return {
        health: getApiUrl('/health'),
        shutdown: getApiUrl('/shutdown'),
        detectCameras: getApiUrl('/freemocap/camera/detect'),
        createGroup: getApiUrl('/freemocap/camera/group/apply'),
        closeAll: getApiUrl('/freemocap/camera/group/close/all'),
        updateConfigs: getApiUrl('/freemocap/camera/update'),
        startRecording: getApiUrl('/freemocap/camera/group/all/record/start'),
        stopRecording: getApiUrl('/freemocap/camera/group/all/record/stop'),
        pauseUnpauseCameras: getApiUrl('/freemocap/camera/group/all/pause_unpause'),
    };
};

export const useAppUrls = {
    getBaseHttpUrl,
    getApiUrl,
    getWebSocketUrl,
    getHttpEndpointUrls,
};
