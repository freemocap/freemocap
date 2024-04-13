<template>
  <div class="sidebar-icon group">
    <slot></slot>
    <span class="sidebar-tooltip group-hover:scale-100">
      {{ text }}
    </span>
  </div>
</template>

<script setup>
const { text } = defineProps({
  text: {
    type: String,
    default: 'wow a tooltipp!'
  }
})
</script>

<style scoped>
.sidebar-icon {
  @apply relative flex items-center justify-center h-12 w-12 mt-2 mb-2 mx-auto shadow-2xl bg-green-950 text-amber-700 rounded-3xl hover:rounded-xl hover:text-white hover:bg-purple-500 transition-all duration-200 ease-in-out cursor-pointer;
}

.sidebar-tooltip {
  @apply absolute w-auto p-2 m-2 min-w-max left-14 rounded-md shadow-md text-white bg-gray-900 text-xs font-bold transition-all duration-100 scale-0 origin-left;
}
</style>
