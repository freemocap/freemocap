export const useCameraGroup = () => {
    const cameraStreams = ref([]);
    const mediaRecorders = ref([]);

    const startCameraGroup = async (cameras: Ref<MediaDeviceInfo[]>) => {
        console.log(`Starting camera group...`);
        try {
            await createCameraStreams(cameras);
            mediaRecorders.value = cameraStreams.value.map((stream: MediaStream) => new MediaRecorder(stream));
        } catch (error) {
            console.error("Error when starting camera group:", error);
        }
    };

    const startRecording = () => {
        console.log("Starting recording...");
        mediaRecorders.value.start();
        mediaRecorders.value.ondataavailable = (event: any) => {
            console.log(event.data)
        };
    };

    const stopRecording = () => {
        console.log("Stopping recording...");
        mediaRecorders.value.forEach((recorder: MediaRecorder) => recorder.stop());
    };

    onUnmounted(() => {
        // Stop all tracks in the group stream

    });

    async function createCameraStreams(cameras: Ref<MediaDeviceInfo[]>) {
        cameraStreams.value = await Promise.all(
            cameras.value.map((camera: MediaDeviceInfo) => {
                const constraints = {
                    video: {
                        deviceId: camera.deviceId ? {exact: camera.deviceId} : undefined,
                        width: {ideal: 1920},
                        height: {ideal: 1080},
                    }
                };
                return navigator.mediaDevices.getUserMedia(constraints);
            })
        );
    }

    return {
        cameraStreams,
        startCameraGroup,
        startRecording,
        stopRecording,
    }
}
