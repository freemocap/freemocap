<template>
  <div class="viewport-container">
    <CameraGrid />
  </div>
</template>

<script setup lang="ts">

</script>


<style scoped>
.viewport-container{
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background-color: #01012d;
}
.overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  pointer-events: none;
}
</style>
