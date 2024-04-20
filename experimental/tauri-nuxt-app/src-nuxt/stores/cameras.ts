interface CameraConfig {
    deviceId: string;
    groupId: string;
    label: string;
    constraints: MediaStreamConstraints;

}

const defaultConstraints: MediaStreamConstraints = {
    video: {
        width: {ideal: 1920},
        height: {ideal: 1080}
    }
};

interface FramePayload {
    imageData: Blob;
    preCaptureTimestamp: DOMHighResTimeStamp;
    postCaptureTimestamp: DOMHighResTimeStamp;
}

export class CameraDevice {
    config: CameraConfig;
    stream: MediaStream | null = null;

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

    public getStream(): MediaStream | null {
        return this.stream;
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
            console.log("Initializing pinia `cameras` store...")
            await this.detectDevices();
            await this.connectToCameras();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices);
            console.log("`Pinia cameras` datastore initialized successfully.")
        },

        async detectDevices() {
            console.log("Detecting available cameras...")
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const videoDevices = devices
                    .filter((device: MediaDeviceInfo) => device.kind === 'videoinput')
                    .filter((device: MediaDeviceInfo) => !device.label.toLowerCase().includes('virtual'));

                this.cameraDevices = videoDevices.map((device: MediaDeviceInfo) => {
                    const config: CameraConfig = {
                        deviceId: device.deviceId,
                        groupId: device.groupId,
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
            console.log(`Available cameras: Cameras - ${this.getCameraLabels}`);
        },

        async connectToCameras() {
            await Promise.all(this.cameraDevices.map((camera: CameraDevice) => camera.connect()));
        },
        async updateCameraConstraints(camera: CameraDevice, constraints: MediaStreamConstraints) {
            console.log(`Updating constraints for camera: ${camera.config.label}`)
            camera.config.constraints = {
                ...camera.config.constraints,
                ...constraints
            };
            await camera.connect();
        },

    },

    getters: {
        getCameraLabels(): string[] {
            return this.cameraDevices.map((camera: CameraDevice) => camera.config.label);
        }
    }
});
