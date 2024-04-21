<template>
  <NuxtLayout>
    <NuxtPage/>
  </NuxtLayout>
</template>

<script setup>
const camerasStore = useCamerasStore();

onMounted(async () => {
  await camerasStore.initialize();
});
</script>
