<template>
  <div class="grid grid-cols-[repeat(auto-fit,_minmax(400px,_1fr))] gap-1 p-1 h-full w-screen ">
    <SingleCameraView
        v-for="camera in cameras"
        :key="camera.deviceId"
        :camera="camera"
        class="w-full h-full object-contain  hover:bg-blue-600 hover:border-blue-800 hover:rounded-3xl transition-all ease-out duration-1000"
    />
    <!--    <ThreeDViewport class="w-full h-full object-contain border-8  border-cyan-800" />-->
  </div>
  <!-- <RecordButton />-->
</template>


<script setup>

const cameras = ref([]);
const cameraViews = ref([]);

const getCameras = async () => {
  try {
    console.log("Getting available cameras");
    const devices = await navigator.mediaDevices.enumerateDevices();
    console.log("All available devices", devices);

    const videoDevices = devices
        .filter((device) => device.kind === "videoinput")
        .filter((device) => !device.label.toLowerCase().includes("virtual"));

    console.log("Filtered video devices", videoDevices);

    cameras.value = videoDevices;

    console.log("Using cameras", cameras.value);
  } catch (error) {
    console.error("Error listing cameras", error);
  }
};


onMounted(() => {
  console.log("Mounted CameraGrid");
  getCameras();
  cameraViews.value = cameras.value.map(() => inject('getStream'));
});
</script>

