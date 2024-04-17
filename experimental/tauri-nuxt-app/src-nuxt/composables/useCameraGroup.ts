export const useCameraGroup = (cameras: Ref<MediaDeviceInfo[]>) => {
    const groupStream = ref(null);
    const mediaRecorder = ref(null);

    const startCameraGroup = async () => {
        console.log(`Starting group camera...`);
        try {
            const streams = await Promise.all(
                cameras.value.map((camera: MediaDeviceInfo) => {
                    const constraints = {
                        video: {
                            deviceId: camera.deviceId ? {exact: camera.deviceId} : undefined,
                        }
                    };
                    return navigator.mediaDevices.getUserMedia(constraints);
                })
            );
            const tracks = streams.flatMap((stream:MediaStream) => stream.getVideoTracks());
            mediaRecorder.value = new MediaRecorder(groupStream.value);
        } catch (error) {
            console.error("Error when starting camera group:", error);
        }
    };

    const startRecording = () => {
        console.log("Starting recording...");
        mediaRecorder.value.start();
        mediaRecorder.value.ondataavailable = (event:any) => {console.log(event.data)};
    };

    const stopRecording = () => {
        console.log("Stopping recording...");
        mediaRecorder.value.stop();
    };

    onUnmounted(() => {
        // Stop all tracks in the group stream
        groupStream.value?.getTracks().forEach((track:MediaStreamTrack) => track.stop());
    });

    return {
        groupStream,
        startGroupCamera: startCameraGroup,
        startRecording,
        stopRecording,
    }
}
