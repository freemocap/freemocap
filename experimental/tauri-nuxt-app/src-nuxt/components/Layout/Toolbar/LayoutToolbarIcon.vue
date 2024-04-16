<template>
  <div class="flex items-center justify-center p-7 m-4 w-12 h-12 bg-blue-400 text-white rounded-3xl cursor-pointer hover:bg-blue-900 group">
    <slot></slot>
    <span class="absolute left-20 bg-gray-900 rounded-lg p-1 scale-0 group-hover:scale-100">
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

