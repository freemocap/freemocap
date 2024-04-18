<template>
  <div
      class="flex items-center justify-center p-7 m-4 w-12 h-12 bg-blue-800 text-white rounded-3xl cursor-pointer hover:bg-blue-400 hover:text-accent group">
    <slot></slot>
    <span class="absolute z-50 left-20 bg-cyan-400 rounded-lg p-1 scale-0 group-hover:scale-100">
      {{ tooltip }}
    </span>
  </div>
</template>


<script setup>
const {tooltip} = defineProps({
  tooltip: {
    type: String,
    default: ""
  },
})
</script>

