<template>
  <TresCanvas window-size v-bind="gl">
    <OrbitControls />
    <TresPerspectiveCamera :position="[0, 0, 5]" />
    <TresAmbientLight color="#ffffff" />
    <TresMesh ref="boxRef" :rotation="[Math.PI/3, Math.PI/2,Math.PI/2, ]" :scale="[2.0,3.5,1.0]">
      <TresBoxGeometry />
      <TresMeshNormalMaterial  />
    </TresMesh>
    <TresGridHelper :size="10" :divisions="10" />
  </TresCanvas>
</template>

<script setup >

import { ref } from 'vue';

const boxRef = ref(null);
console.log(`boxRef:`, boxRef)


const { onLoop } = useRenderLoop()

onLoop(({ delta, elapsed, clock, dt }) => {
  // I will run at every frame ~ 60FPS (depending of your monitor)
  if(boxRef.value) {
    boxRef.value.rotation.y += delta * 0.1;
    boxRef.value.rotation.z = elapsed * 0.1;
    boxRef.value.rotation.x = delta * 0.1;
  }
})
const gl = reactive({
  clearColor: '#125042',
})
// const { pane } = useTweakPane()
// pane.addInput(gl, 'clearColor', { label: 'Background' })
</script>
