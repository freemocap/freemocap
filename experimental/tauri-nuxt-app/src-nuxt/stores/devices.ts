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
            console.log(`Detected devices: \n Cameras: [${JSON.stringify(this.cameras, null, 2)}],\n Microphones: [${JSON.stringify(this.microphones, null, 2)}], \n Speakers: [${JSON.stringify(this.speakers, null, 2)}]`)
        },
        initialize() {
            console.debug("Initializing `devices` store...")
            this.detectDevices()
            navigator.mediaDevices.addEventListener('devicechange', this.detectDevices)
        }
    },
    getters: {}
})
