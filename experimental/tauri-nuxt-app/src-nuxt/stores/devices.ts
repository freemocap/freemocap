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
            this.logAvailableDevices();
        },
        initialize() {
            console.log("Initializing `devices` pinia store")
            this.detectDevices();
            navigator.mediaDevices.addEventListener('devicechange', () => this.detectDevices);
            console.log("`devices` datastore initialized successfully.")
        },

        logAvailableDevices() {
            const cameraCount = this.availableCameras.length;
            const micCount = this.devices.filter((device: MediaDeviceInfo) => device.kind === 'audioinput').length;
            const speakerCount = this.devices.filter((device: MediaDeviceInfo) => device.kind === 'audiooutput').length;

            console.log(`Available devices: Cameras - ${cameraCount}, Microphones - ${micCount}, Speakers - ${speakerCount}`);
        }
    },
    getters: {
        availableCameras: (state) => state.devices.filter((device: MediaDeviceInfo) => device.kind === 'videoinput'),


    }
});
