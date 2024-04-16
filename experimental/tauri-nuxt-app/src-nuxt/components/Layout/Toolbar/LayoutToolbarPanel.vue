<script setup>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { library } from '@fortawesome/fontawesome-svg-core';
import { faFire, faPlus, faBoltLightning, faGear, faPoo } from '@fortawesome/free-solid-svg-icons';

library.add(faFire, faPlus, faBoltLightning, faGear, faPoo);

</script>

<template>
  <div
      class="w-20 m-0 flex flex-col bg-primary text-gray-300 text-2xl justify-center items-center shadow-2xl border-green-600 border-4">
    <LayoutToolbarIcon><FontAwesomeIcon :icon="['fas', 'skull']" size="lg" /></LayoutToolbarIcon>
    <LayoutToolbarIcon><FontAwesomeIcon :icon="['fas', 'camera']" size="lg" /></LayoutToolbarIcon>
    <LayoutToolbarIcon><FontAwesomeIcon :icon="['fas', 'poo']" size="lg" /></LayoutToolbarIcon>
    <LayoutToolbarIcon><FontAwesomeIcon :icon="['fas', 'gear']" size="lg" /></LayoutToolbarIcon>
  </div>
</template>

<style scoped>

</style>
