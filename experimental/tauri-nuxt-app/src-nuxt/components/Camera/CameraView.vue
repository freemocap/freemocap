<template>
  <div class="relative w-full h-full overflow-hidden">
    <video
        ref="video"
        autoplay
        class="absolute top-0 left-0 w-full h-full object-contain"
        muted
        @loadedmetadata="onLoadedMetadata"
    ></video>
  </div>
</template>

<script setup>


const props = defineProps({
  cameraDevice: CameraDevice,
});
const video = ref(null);

watch(
    () => props.cameraDevice,
    (newVal) => {
      if (newVal) {
        video.value = props.cameraDevice.createVideoElement();
      }
    }
);

onMounted(() => {
  if (props.cameraDevice) {
    console.log(`Mounting 'CameraView' component with camera: ${props.cameraDevice.label}...`)
    video.value = props.cameraDevice.createVideoElement();
  }
})
</script>

