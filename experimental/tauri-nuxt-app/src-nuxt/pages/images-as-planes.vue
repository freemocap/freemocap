<template>
  <TresCanvas v-bind="gl">
    <OrbitControls/>
    <TresPerspectiveCamera :position="[0, 0, 10]"/>
<!--    <TresMesh :rotation="[0, 0, 0]" :scale="[1.0, 1.0, 1.0]">-->
    <TresMesh v-for="(texture, index) in videoTextures" :key="index" :position="[index * 2 - (videoTextures.length -1),0,0]" :rotation="[0,0,0]">
      <TresPlaneGeometry :args="[16, 9]"/>
      <TresMeshBasicMaterial :map="texture"/>
    </TresMesh>
    <TresGridHelper :divisions="100" :size="100"/>
  </TresCanvas>
</template>

<script setup lang="ts">
import * as THREE from 'three';
const camerasStore = useCamerasStore();
const videoTextures = ref<THREE.Texture[]>([]);

const gl = reactive({
  clearColor: '#0c352c',
  antialias: true,
});


onMounted(async () => {
  for (let i = 0; i < camerasStore.cameraDevices.length; i++) {
    const video = document.createElement('video');
    video.autoplay = true;
    video.style.display = 'none';
    document.body.appendChild(video);

    video.srcObject = await camerasStore.cameraDevices[i].getStream();
    video.play();

    const texture = new THREE.VideoTexture(video);
    videoTextures.value.push(texture);
  }

});
</script>

<style scoped>
canvas {
  display: block; /* Remove canvas margin */
}
</style>
