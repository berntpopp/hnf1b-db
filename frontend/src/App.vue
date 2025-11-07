<template>
  <v-app>
    <AppBar />
    <v-main>
      <router-view />
    </v-main>
    <FooterBar />
    <LogViewer />
  </v-app>
</template>

<script>
import AppBar from './components/AppBar.vue';
import FooterBar from './components/FooterBar.vue';
import LogViewer from './components/LogViewer.vue';

export default {
  name: 'App',
  components: {
    AppBar,
    FooterBar,
    LogViewer,
  },
};
</script>
