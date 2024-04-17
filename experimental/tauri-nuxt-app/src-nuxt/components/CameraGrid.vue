<template>
  <div class="grid grid-cols-[repeat(auto-fit,_minmax(400px,_1fr))] gap-1 p-1 h-full w-screen ">
    <CameraView
        v-for="camera in cameras"
        :key="camera.deviceId"
        :camera="camera"
        class="w-full h-full object-contain  hover:bg-blue-600 hover:border-blue-800 hover:rounded-3xl transition-all ease-out duration-1000"
    />
  </div>
</template>


<script setup>

const devicesStore = useDevicesStore();
const cameras = ref([]);

onMounted(async () => {
  console.log("Mounting CameraGrid...");
  await devicesStore.initialize()
  cameras.value = devicesStore.availableCameras
  console.log(`CameraGrid mounted successfully - ${cameras.length} cameras found`)
});
</script>

