export const useCameraDevice =  (camera: Ref<MediaDeviceInfo>) => {
    const video = ref(null);
    const stream = ref(null);

    const startCamera = async () => {
        console.log(`Starting camera: ${camera.value.label} (${camera.value.deviceId})`);
        try {
            const constraints = {
                video: {
                    deviceId: camera.value.deviceId ? {exact: camera.value.deviceId} : undefined,
                    width: {ideal: 1920},
                    height: {ideal: 1080},
                },
            };
            stream.value = await navigator.mediaDevices.getUserMedia(constraints);
            if (video.value) {
                video.value.srcObject = stream.value;
            }
        } catch (error) {
            console.error("Error when accessing webcam:", error);
        }
    };

    const stopCamera = () => {
        if (video.value && video.value.srcObject) {
            const tracks = video.value.srcObject.getTracks();
            tracks.forEach((track: MediaStreamTrack) => track.stop());
            video.value.srcObject = null;
        }
    };
    onUnmounted(() => {
        stopCamera();
    });

    return {
        video,
        stream,
        startCamera,
        stopCamera,
    }
}
