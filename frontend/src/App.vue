<template>
  <v-app>
    <AppBar />
    <v-main>
      <router-view />
    </v-main>
    <FooterBar />
  </v-app>
</template>

<script>
import AppBar from './components/AppBar.vue';
import FooterBar from './components/FooterBar.vue';

export default {
  name: 'App',
  components: {
    AppBar,
    FooterBar,
  },
};
</script>
