<script setup>
import {FontAwesomeIcon} from '@fortawesome/vue-fontawesome';
import {library} from '@fortawesome/fontawesome-svg-core';
import {faCamera, faFire, faGear, faHome, faPlus, faPoo, faSkull} from '@fortawesome/free-solid-svg-icons';

library.add(faFire, faPlus, faCamera, faGear, faPoo, faSkull, faHome);

</script>

<template>
  <div
      class="w-20 m-0 flex flex-col bg-primary text-gray-300 text-2xl justify-center items-center shadow-2xl">

    <LayoutToolbarIcon>
      <NuxtLink to="/">
        <FontAwesomeIcon :icon="['fas', 'house']" size="lg"/>
      </NuxtLink>
    </LayoutToolbarIcon>

    <LayoutToolbarIcon>
      <NuxtLink to="/camera-group">
        <FontAwesomeIcon :icon="['fas', 'camera']" size="lg"/>
      </NuxtLink>
    </LayoutToolbarIcon>

    <LayoutToolbarIcon>
      <NuxtLink to="/three-d-viewport">
        <FontAwesomeIcon :icon="['fas', 'skull']" size="lg"/>
      </NuxtLink>
    </LayoutToolbarIcon>


    <LayoutToolbarIcon>
      <FontAwesomeIcon :icon="['fas', 'gear']" size="lg"/>
    </LayoutToolbarIcon>
  </div>
</template>

<style scoped>

</style>
