<template>
  <NuxtLayout>
    <v-app id="inspire" class="bg-grey-darken-4">
      <NuxtPage/>
    </v-app>
  </NuxtLayout>

</template>

<script setup>
const camerasStore = useCamerasStore();

onMounted(async () => {
  await camerasStore.initialize();
});
</script>
