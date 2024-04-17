export const useDevicesStore = defineStore('devices', {
    state: () => ({
        cameras: [],
        microphones: [],
        speakers: [],
    }),

    actions: {
        async detectDevices() {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.cameras = devices.filter(device => device.kind === 'videoinput')
            this.microphones = devices.filter(device => device.kind === 'audioinput')
            this.speakers = devices.filter(device => device.kind === 'audiooutput')
        },
        initialize() {
            console.debug("Initializing `devices` store...")
            this.detectDevices()
            navigator.mediaDevices.addEventListener('devicechange', this.detectDevices)
        }
    },
    getters: {}
})
