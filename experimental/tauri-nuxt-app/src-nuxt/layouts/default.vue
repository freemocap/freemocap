<template>
  <div class="flex flex-col ">

    <header class=" bg-blue-400">
      <LayoutHeader/>
    </header>

    <main class="flex flex-1">
      <LayoutToolbarPanel/>
        <slot/>
    </main>

    <footer>
      <LayoutFooter class="bg-blue-900"/>
    </footer>
  </div>
</template>
<script setup lang="ts">
</script>
