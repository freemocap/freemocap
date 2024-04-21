

const defaultConstraints: MediaStreamConstraints = {
    video: {
        width: { ideal: 1920 },
        height: { ideal: 1080 }
    }
};

export class CameraDevice {
    cameraNumber: string;
    deviceInfo: MediaDeviceInfo;
    stream: MediaStream | null = null;
    targetConstraints: Object | null = null;
    currentSettings: MediaTrackSettings | null = null;
    capabilities: MediaTrackCapabilities | null = null;

    constructor(deviceInfo:MediaDeviceInfo, cameraNumber: string) {
        this.cameraNumber = cameraNumber;
        this.deviceInfo = deviceInfo;
    }

    async connect() {
        this.targetConstraints = {
            video: {
                deviceId: { exact: this.deviceInfo.deviceId } }
        };
        try {
            this.stream = await navigator.mediaDevices.getUserMedia(this.targetConstraints);
            this.currentSettings = this.stream.getVideoTracks()[0].getSettings();
            this.capabilities = this.stream.getVideoTracks()[0].getCapabilities();
            console.log(`Connected to Camera#${this.cameraNumber} - ${this.deviceInfo.label}`);
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

    state: (): { camerasReady: boolean; cameraDevices: any[] } => ({
        cameraDevices: [],
        camerasReady: false,
    }),

    actions: {
        async initialize() {
            if (this.camerasReady) {
                console.log("Cameras are already initialized.");
                return;
            }
            console.log("Initializing pinia `cameras` store...")
            await this.detectDevices();
            await this.connectToCameras();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices);
            this.camerasReady = true;
            console.log("`Pinia cameras` datastore initialized successfully.")
        },

        async detectDevices() {
            console.log("Detecting available cameras...")
            let cameraNumber = -1
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                console.log(`Found ${devices.length} camera(s) - \n ${JSON.stringify(devices, null, 2)}`);

                const videoDevices = devices
                    .filter((device: MediaDeviceInfo) => device.kind === 'videoinput')
                    .filter((device: MediaDeviceInfo) => !device.label.toLowerCase().includes('virtual'));
                this.cameraDevices = videoDevices.map((deviceInfo: MediaDeviceInfo) => {
                    cameraNumber++;
                    return new CameraDevice(deviceInfo, String(cameraNumber));
                });
            } catch (error) {
                console.error('Error when detecting cameras:', error);
            }
            console.log(`Found ${this.cameraDevices.length} camera(s) - \n ${JSON.stringify(this.cameraDevices, null, 2)}`);
        },

        async connectToCameras() {
            await Promise.all(this.cameraDevices.map((camera: CameraDevice) => camera.connect()));
        },

    },

});
