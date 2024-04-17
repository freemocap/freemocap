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
            console.log(`Detected devices: \n Cameras: [${JSON.stringify(this.cameras, null, 2)}],\n Microphones: [${this.microphones}], \n Speakers: [${this.speakers}]`)
        },
        initialize() {
            this.detectDevices()
            navigator.mediaDevices.addEventListener('devicechange', this.detectDevices)
        }
    },
    getters: {
    }
})
