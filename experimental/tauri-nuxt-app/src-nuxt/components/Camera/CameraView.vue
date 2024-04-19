<template>
  <div class="relative">
    <video
        ref="videoElement"
        autoplay
        class="absolute top-0 left-0 w-full h-full object-contain"
        muted
        playsinline
    ></video>
  </div>
</template>

<script setup>


const props = defineProps({
  cameraDevice: CameraDevice,
});
const videoElement = ref(null);
const cameraStream = computed(() => props.cameraDevice.getStream());

watch(
    cameraStream,
    (newStream) => {
      if (newStream && videoElement.value) {
        videoElement.value.srcObject = newStream;
      }
    },
    { immediate: true }
);

onMounted(() => {
  if (videoElement.value && cameraStream.value) {
    videoElement.value.srcObject = cameraStream.value;
  }
});
</script>

