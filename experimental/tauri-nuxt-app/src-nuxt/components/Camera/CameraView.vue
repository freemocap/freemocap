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
  camera: Object
});
const {video, startCamera} = useCameraDevice(ref(props.camera));

watch(
    () => props.camera,
    (newVal) => {
      if (newVal) {
        startCamera();
      }
    }
);

onMounted(() => {
  console.log(`Mounting 'CameraView' component with camera: ${props.camera.label}...`)
  if (props.camera) {
    startCamera();
  }
})
</script>

