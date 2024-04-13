<template>
  <div class="viewport-container">

    <ThreeDViewport />
    <div >
      <CameraGrid />
    </div>
  </div>
</template>

<script setup lang="ts">

</script>


<style scoped>
.viewport-container{
  @apply relative w-full h-screen overflow-hidden bg-secondary;
}
.overlay {
  @apply absolute top-0 left-0 w-full h-screen pointer-events-none;
}
</style>
