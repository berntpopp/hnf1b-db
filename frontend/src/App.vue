<template>
  <v-app>
    <AppBar @toggle-drawer="drawer = !drawer" />
    <MobileDrawer v-model="drawer" />
    <v-main>
      <router-view />
    </v-main>
    <FooterBar />
    <LogViewer />
  </v-app>
</template>

<script setup>
import { ref } from 'vue';
import AppBar from './components/AppBar.vue';
import MobileDrawer from './components/MobileDrawer.vue';
import FooterBar from './components/FooterBar.vue';
import LogViewer from './components/LogViewer.vue';

// Mobile navigation drawer state
const drawer = ref(false);
</script>
