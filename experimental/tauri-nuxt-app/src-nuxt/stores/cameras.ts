export const useCamerasStore = defineStore('cameras', {

    state: (): { cameras: MediaDeviceInfo[] } => ({
        cameras: [],
    }),

    actions: {
        async initialize() {
            console.log("Initializing `cameras` pinia store")
            await this.detectDevices();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices);
            console.log("`cameras` datastore initialized successfully.")
        },
        async detectDevices() {
            console.log("Detecting available cameras...")
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                this.cameras = devices.filter((device: MediaDeviceInfo) => device.kind === 'videoinput');
            } catch (error) {
                console.error('Error when detecting cameras:', error);
            }
            console.log(`Available cameras: Cameras - ${this.cameras.map((camera: MediaDeviceInfo) => camera.label).join(', ')}`);
        },

    },
    getters: {
    }
});
