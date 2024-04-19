<template>
  <div class="grid grid-cols-[repeat(auto-fit,_minmax(400px,_1fr))] gap-1 p-1 h-full w-screen ">
    <CameraView
        v-for="camera in cameraDevices"
        :key="camera.name"
        :camera="camera"
        class="w-full h-full object-contain  hover:bg-blue-600 hover:border-blue-800 hover:rounded-3xl transition-all ease-out duration-1000"
    />
  </div>
</template>


<script setup>

const camerasStore = useCamerasStore();
const cameraDevices = ref([]);

watch(() => camerasStore.cameraDevices, (newVal) => {
  if (newVal) {
    cameraDevices.value = camerasStore.cameraDevices;
    console.log(`Updated cameras - ${cameraDevices.value.length} cameras found`);
  }
});

onMounted(async () => {
  console.log("Mounting CameraGrid...");
  await camerasStore.initialize();
});
</script>

