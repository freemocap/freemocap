<template>
  <NuxtLayout class="h-screen w-screen overflow-hidden">
    <NuxtPage/>
  </NuxtLayout>
</template>

<script setup>
const camerasStore = useCamerasStore();

onMounted(async () => {
  console.log("Initializing Cameras Store...");
  await camerasStore.initialize();
});
</script>
