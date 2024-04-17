export const useDevicesStore = defineStore('devices', {
    state: (): { devices: MediaDeviceInfo[] } => ({
        devices: [],
    }),

    actions: {
        async detectDevices() {
            console.log("Detecting available devices...")
            try {
                this.devices = await navigator.mediaDevices.enumerateDevices();
            } catch (error) {
                console.error('Error when detecting devices:', error);
            }
            console.log(`Found: ${this.devices.length} devices`);
        },
        initialize() {
            console.log("Initializing `devices` pinia store")
            this.detectDevices();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices());
            console.log("`devices` datastore initialized successfully.")
        }
    },
    getters: {
        availableCameras: (state) => state.devices.filter((device: MediaDeviceInfo) => device.kind === 'videoinput')
    }
});
