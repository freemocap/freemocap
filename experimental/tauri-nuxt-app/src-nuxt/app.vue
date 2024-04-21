<template>
  <NuxtLayout>
    <v-app id="inspire" class="bg-grey-darken-4">
      <NuxtPage/>
    </v-app>
  </NuxtLayout>

</template>

<script setup>
const camerasStore = useCamerasStore();


await onMounted(async () => {
  console.log('Calling `camerasStore.initialize()`...');
  await camerasStore.initialize();
  console.log('Call to `camerasStore.initialize()` completed successfully!');
})


</script>
