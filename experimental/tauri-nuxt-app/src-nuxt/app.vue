<template>
  <NuxtLayout class="h-screen w-screen overflow-hidden">
    <NuxtPage/>
  </NuxtLayout>
</template>

<script setup>
const camerasStore = useCamerasStore();

onMounted(async () => {
  await camerasStore.initialize();
});
</script>
