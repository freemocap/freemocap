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
