<script setup lang="ts">

</script>
<template>
  <div class="flex flex-col h-screen">
    <header>
      <LayoutHeader/>
    </header>
    <main class="flex flex-1 overflow-hidden">
      <LayoutToolbarPanel/>
      <slot/>
    </main>
    <footer >
      <LayoutFooter/>
    </footer>
  </div>
</template>
<style scoped>

</style>
