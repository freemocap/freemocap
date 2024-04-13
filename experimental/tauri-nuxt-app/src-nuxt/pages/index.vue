<template>
  <div class="flex">


    <div class="flex-1 bg-purple-400 ">
      <div class="relative overflow-hidden bg-secondary">
        <ThreeDViewport/>
      </div>
      <div class="relative top-0 left-0 pointer-events-none">
        <CameraGrid/>
      </div>
    </div>

    <div class="flex-1 bg-primary">
      <SideBar/>
    </div>
  </div>
</template>w3hat

<script setup lang="ts">
</script>
