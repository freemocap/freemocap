interface CameraConfig {
    deviceId: string;
    label: string;
    constraints: MediaStreamConstraints;

}
const defaultConstraints: MediaStreamConstraints = {
    video: {
        width: {ideal: 1920},
        height: {ideal: 1080}
    }
};

export class CameraDevice {
    private config: CameraConfig;
    private stream: MediaStream | null = null;

    constructor(config: CameraConfig) {
        // Merge default constraints with provided constraints
        this.config = {
            ...config,
            constraints: {
                ...defaultConstraints,
                ...config.constraints
            }
        };
    }

    async connect() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia(this.config.constraints);
            console.log(`Connected to camera: ${this.config.label}`);
        } catch (error) {
            console.error('Error when connecting to camera:', error);
        }
    }
    async createVideoElement() {
        const video = document.createElement('video');
        if (this.stream) {
            video.srcObject = this.stream;
        }
        return video;
    }
    disconnect() {
        this.stream?.getTracks().forEach(track => track.stop());
    }

}

export const useCamerasStore = defineStore('cameras', {

    state: (): { cameraDevices: CameraDevice[] } => ({
        cameraDevices: [],
    }),

    actions: {
        async initialize() {
            console.log("Initializing `cameras` pinia store")
            await this.detectDevices();
            await this.connectToCameras();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices);
            console.log("`cameras` datastore initialized successfully.")
        },

        async detectDevices() {
            console.log("Detecting available cameras...")
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = devices.filter((device: MediaDeviceInfo) => device.kind === 'videoinput');

                this.cameraDevices = videoDevices.map((device: MediaDeviceInfo) => {
                    const config: CameraConfig = {
                        deviceId: device.deviceId,
                        label: device.label,
                        constraints: {
                            video: {
                                deviceId: device.deviceId ? {exact: device.deviceId} : undefined,
                            },
                        },
                    };
                    return new CameraDevice(config);
                });
            } catch (error) {
                console.error('Error when detecting cameras:', error);
            }
            console.log(`Available cameras: Cameras - ${this.cameraDevices.map((camera: MediaDeviceInfo) => camera.label).join(', ')}`);
        },

        async connectToCameras() {
            await Promise.all(this.cameraDevices.map((camera: CameraDevice) => camera.connect()));
        },
    },

    getters: {}
});
