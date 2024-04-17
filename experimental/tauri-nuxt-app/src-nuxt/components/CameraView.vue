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
const props = defineProps({
  camera: Object
});
const {video, startCamera} = useCamera(ref(props.camera));

watch(
    () => props.camera,
    (newVal) => {
      if (newVal) {
        startCamera();
      }
    }
);

onMounted(() => {
  console.log(`Mounting 'CameraView' component with ${JSON.stringify(props.camera, null, 2)}...`)
  if (props.camera) {
    startCamera();
  }
})
</script>

