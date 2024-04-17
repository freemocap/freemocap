export default (camera:MediaDeviceInfo) => {
    const video = ref(null);
    const stream = ref(null);

    const startCamera = async () => {
        try {
            const constraints = {
                video: {
                    deviceId: camera.value ? {exact: camera.value.deviceId} : undefined,
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

    const stopWebcam = () => {
        if (video.value && video.value.srcObject) {
            const tacks = video.value.srcObject.getTracks();
            tracks.forEach(track=> track.stop());
            video.value.srcObject= null;
        }
    };
    onUnmounted(() => {
        stopWebcam();
    });

    return {
        video,
        stream,
        startWebcam,
        stopWebcam,
    }
}
