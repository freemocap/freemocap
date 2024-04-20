<template>
  <div class="bg-secondary flex-grow justify-center">
    <div class="flex flex-col items-center justify-center gap-8 m-16">
      <button class="nuxt-link-button">
        <NuxtLink to="/images-as-planes">Images as Planes</NuxtLink>
      </button>
      <button class="nuxt-link-button">
        <NuxtLink to="/camera-group">Camera Group</NuxtLink>
      </button>
      <button class="nuxt-link-button">
        <NuxtLink to="/three-d-viewport">Three D Viewport</NuxtLink>
      </button>
    </div>
  </div>
</template>

<style scoped>
.nuxt-link-button {
  @apply text-cyan-400 bg-blue-900 rounded-full shadow-xl text-4xl hover:text-accent p-6 hover:text-5xl transition-all duration-1000;
}
</style>
<script setup lang="ts">
</script>
