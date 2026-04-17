<template>
  <v-app>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <AppBar @toggle-drawer="drawer = !drawer" />
    <MobileDrawer v-model="drawer" />
    <v-main id="main-content">
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

<style>
/* Global (unscoped): the skip link must be the first focusable element and
   appear above all Vuetify chrome when focused, so the z-index + transform
   apply globally without a scoped attribute selector. */
.skip-link {
  position: absolute;
  top: 0;
  left: 0;
  padding: 8px 12px;
  background: #00695c;
  color: #ffffff;
  text-decoration: none;
  z-index: 10000;
  transform: translateY(-120%);
  transition: transform 0.15s ease-in-out;
}
.skip-link:focus {
  transform: translateY(0);
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}
</style>
