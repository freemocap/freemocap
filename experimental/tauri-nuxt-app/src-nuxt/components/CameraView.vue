<template>
  <div class="relative w-full h-full overflow-hidden">
    <video
        ref="video"
        @loadedmetadata="onLoadedMetadata"
        autoplay
        muted
        class="absolute top-0 left-0 w-full h-full object-contain"
    ></video>
  </div>
</template>

<script setup>
import {onMounted, onUnmounted, ref, watch} from 'vue';

const props = defineProps({
  camera: Object,
});

const video = ref(null);
const stream = ref(null);




const startWebcam = async () => {
  try {
    const constraints = {
      video: {
        deviceId: props.camera ? { exact: props.camera.deviceId } : undefined,
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      },
    };
    stream.value = await navigator.mediaDevices.getUserMedia(constraints);
    if (video.value) {
      video.value.srcObject = stream.value;
    }

  } catch (error) {
    console.error("Error accessing the webcam", error);
  }
};

watch(
    () => props.camera,
    (newVal, oldVal) => {
      if (newVal !== oldVal) {
        startWebcam();
      }
    },
    { immediate: true }
);

onMounted(() => {
  if (props.camera) {
    startWebcam();
  }
});

onUnmounted( () => {
  if (video.value && video.value.srcObject) {
    console.log("Stopping stream");
    const tracks = video.value.srcObject.getTracks();
    tracks.forEach(track => track.stop());
    video.value.srcObject = null;

  }
});
</script>

