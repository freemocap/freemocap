<template>
  <div class="toolbar-icon group">
    <slot></slot>
    <span class="toolbar-tooltip group-hover:scale-100">
      {{ text }}
    </span>
  </div>
</template>

<script setup>

const {text} = defineProps({
  text: {
    type: String,
    default: "wow a tooltipp!"
  },
})

</script>


<style scoped>
.toolbar-icon {
  @apply flex items-center justify-center w-12 h-12 bg-primary text-white rounded-lg cursor-pointer;
  position: relative;
}

.toolbar-tooltip {
  @apply absolute top-0 left-0 transform scale-0 bg-black text-white p-2 rounded-lg;
  transition: transform 0.2s;
  transform-origin: 100% 0;
  display: none;
}

</style>


