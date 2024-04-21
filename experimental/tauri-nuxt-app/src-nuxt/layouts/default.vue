<template>
  <v-app id="inspire" class="bg-grey-darken-4">
    <v-navigation-drawer v-model="drawer" app :rail="rail" class="bg-cyan-darken-4">
      <v-list class="pa-0">
        <v-list-item :class="drawer ? 'justify-end' : 'justify-center'" class="px-3 d-flex" @click="toggleRail">
          <v-icon large class="clickable">
            {{ railIcon }}
          </v-icon>
        </v-list-item>

        <v-list-item link to="/" class="px-3 d-flex" :class="drawer ? 'justify-start' : 'justify-center'">
          <v-icon large>mdi-home</v-icon>
        </v-list-item>

        <v-list-item link to="/images-as-planes" class="px-3 d-flex" :class="drawer ? 'justify-start' : 'justify-center'">
          <v-icon large>mdi-skull</v-icon>
        </v-list-item>

        <v-list-item link to="/camera-group" class="px-3 d-flex" :class="drawer ? 'justify-start' : 'justify-center'">
          <v-icon large>mdi-camera</v-icon>
        </v-list-item>

        <v-list-item link to="/three-d-viewport" class="px-3 d-flex" :class="drawer ? 'justify-start' : 'justify-center'">
          <v-icon large>mdi-cube</v-icon>
        </v-list-item>

      </v-list>
    </v-navigation-drawer>

    <v-main>
      <slot/>
    </v-main>

  </v-app>
</template>

<script setup>

const drawer = ref(true);
const rail = ref(true);

const railIcon = computed(() => (rail.value ? 'mdi-menu' : 'mdi-chevron-left'));

const toggleRail = () => {
  console.log('toggleRail');
  rail.value = !rail.value;

  if (rail.value) {
    drawer.value = true;
  }
}
</script>

<style>
.clickable {
  cursor: pointer;
}
</style>
