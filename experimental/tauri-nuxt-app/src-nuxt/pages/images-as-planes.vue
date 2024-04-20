<template>
  <TresCanvas v-bind="gl">
    <OrbitControls/>
    <TresPerspectiveCamera :position="[0, 1, 5]"/>
<!--    <TresMesh :rotation="[0, 0, 0]" :scale="[1.0, 1.0, 1.0]">-->
    <TresMesh v-for="(texture, index) in videoTextures" :key="index" :position="cameraPositions[index]" :rotation="[0,0,0]">
      <TresPlaneGeometry :args="[1.6, .9]"/>
      <TresMeshBasicMaterial :map="texture"/>
    </TresMesh>
    <TresGridHelper :divisions="100" :size="100"/>
  </TresCanvas>
</template>

<script setup lang="ts">
import * as THREE from 'three';
const camerasStore = useCamerasStore();
const videoTextures = ref<THREE.Texture[]>([]);

const planeWidth:number = 1.6;
const planeHeight:number = .9;
const planeSpacing:number = 0.1;

// Define the type for the array of positions
type Position = [number, number, number];
type CameraPositions = ComputedRef<Position[]>;

const cameraPositions: CameraPositions = computed(() => {
  return videoTextures.value.map((_:any, index:number, array:THREE.Texture[]): Position => {
    const offset: number = (planeWidth + planeSpacing) * (array.length - 1) / 2;
    return [(index * (planeWidth + planeSpacing)) - offset, 0, 0];
  });
});
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
