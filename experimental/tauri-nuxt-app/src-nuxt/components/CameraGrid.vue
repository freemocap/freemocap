<template>
  <div class="webcam-grid">
    <SingleCameraView
        v-for="camera in cameras"
        :key="camera.deviceId"
        :camera="camera"
    />
  </div>
<!--  < <RecordButton />-->
</template>

<script setup>
import {ref, onMounted, inject} from "vue";

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
  cameraViews.value = cameras.value.map( () => inject('getStream'));
});
</script>

<style>
.webcam-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 10px;
  padding: 10px;
  height: 100vh;
  width: 100vw;
  box-sizing: border-box;
  overflow: auto;
  border: #0a21a9 2px solid;
}


.camera-container video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border: darkgreen 2px solid;
}


</style>
