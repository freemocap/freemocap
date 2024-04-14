<script setup>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { library } from '@fortawesome/fontawesome-svg-core';
import { faFire, faPlus, faBoltLightning, faGear, faPoo } from '@fortawesome/free-solid-svg-icons';

library.add(faFire, faPlus, faBoltLightning, faGear, faPoo);

import SideBarIcon from "@/components/SideBarIcon.vue";
</script>

<template>
  <div
      class="h-screen w-20 m-0 flex flex-col bg-primary text-gray-300 text-2xl justify-center items-center shadow-2xl border-green-600 border-8">
    <SideBarIcon><FontAwesomeIcon :icon="['fas', 'skull']" size="lg" /></SideBarIcon>
    <SideBarIcon><FontAwesomeIcon :icon="['fas', 'camera']" size="lg" /></SideBarIcon>
    <SideBarIcon><FontAwesomeIcon :icon="['fas', 'gear']" size="lg" /></SideBarIcon>
    <SideBarIcon><FontAwesomeIcon :icon="['fas', 'poo']" size="lg" /></SideBarIcon>
  </div>
</template>

<style scoped>

</style>
