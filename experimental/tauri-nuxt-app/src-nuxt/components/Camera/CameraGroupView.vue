<template>
  <v-container fluid class="pa-1">
    <v-row>
      <v-col
          v-for="cameraDevice in camerasStore.cameraDevices"
          :key="cameraDevice.name"
      >
        <CameraView
            :cameraDevice="cameraDevice"
            class="w-full h-full transition-swing"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
const camerasStore = useCamerasStore();
</script>

<style>
/* Example of a simple hover effect */
.transition-swing:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  cursor: pointer;
}
</style>
