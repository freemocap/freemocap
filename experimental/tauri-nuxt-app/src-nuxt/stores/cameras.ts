// TODO - better wrangle `stream`, `track`, config (constraints), `available settings` and `devicechange` event and other listeners, and a bunch of other stuff for each camera indifgivually, and also a way to interact with all the cameras as a group
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

        async connectToCameras() {
            console.log("Connecting to cameras...")
            try {
                await Promise.all(this.cameras.map(async (camera: MediaDeviceInfo) => {
                    //TODO - make a camera model that holds this info and can be passed to the composable
                    const constraints = {
                        video: {
                            deviceId: camera.deviceId ? {exact: camera.deviceId} : undefined,
                            width: {ideal: 1920},
                            height: {ideal: 1080},
                        },
                        //TODO - also record audio
                    };
                    const stream = await navigator.mediaDevices.getUserMedia(constraints);
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    video.autoplay = true;
                    document.body.appendChild(video);
                }));
            } catch (error) {
                console.error("Error when connecting to cameras:", error);
            }
        }
    },


    getters: {

    }
});
