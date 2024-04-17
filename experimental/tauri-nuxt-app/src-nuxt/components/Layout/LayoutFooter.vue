<script lang="ts" setup>
const foot = ['🦶', '🦶', '🦶']
</script>

<template>
  <div class="flex justify-center items-center ">
    <span v-for="(item, index) in foot" :key="index" class="mx-24">{{ item }}</span>
  </div>
</template>

<style scoped>

</style>
