<template>
  <v-app id="inspire" class="bg-grey-darken-4">
    <v-navigation-drawer v-model="drawerVisible" permanent app class="bg-cyan-darken-4">
      <!--  -->
    </v-navigation-drawer>

    <v-app-bar class="bg-teal-darken-4">
      <v-app-bar-nav-icon @click="drawerVisible = !drawerVisible"></v-app-bar-nav-icon>

      <v-app-bar-title>FreeMoCap</v-app-bar-title>
    </v-app-bar>

    <v-main>
      <slot />
    </v-main>
  </v-app>
</template>

<script setup>
const drawerVisible = ref(false)
</script>
