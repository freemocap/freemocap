<template>
  <div>
    <h1>Camera Status</h1>
    <p>Cameras Ready: {{ camerasReady }}</p>

    <h2>Available Cameras:</h2>
    <ul>
      <li v-for="(camera, index) in camerasStore.cameraDevices" :key="index">
        {{ camera.deviceInfo.label }} - {{ camera.cameraNumber }}
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';

const camerasStore = useCamerasStore();
const camerasReady = ref(false);
const cameraDevices = ref([]);

onMounted(async () => {
  await camerasStore.initialize();
  camerasReady.value = camerasStore.camerasReady;
});
</script>









