<script setup lang="ts">
const foot = ['🦶', '🦶', '🦶']
</script>

<template>
  <div class="flex justify-center items-center border-red-900 border-4 bg-blue-900">
    <span v-for="(item, index) in foot" :key="index" class="mx-24">{{ item }}</span>
  </div>
</template>

<style scoped>

</style>
