<template>
  <v-footer app padless class="elevation-3">
    <v-card-text class="text-center">
      <v-btn
        v-for="link in footerLinks"
        :key="link.text"
        icon
        :href="link.href"
        :target="link.target"
        text
      >
        <v-icon size="24px">
          {{ link.icon }}
        </v-icon>
      </v-btn>
    </v-card-text>
  </v-footer>
</template>

<script>
export default {
  name: 'FooterBar',
  data() {
    return {
      footerLinks: [
        {
          text: 'GitHub',
          icon: 'mdi-github',
          href: 'https://github.com/berntpopp/HNF1B-db',
          target: '_blank',
        },
        {
          text: 'API',
          icon: 'mdi-api',
          href: '/API',
          target: '_self',
        },
        {
          text: 'License',
          icon: 'mdi-copyright',
          href: 'https://creativecommons.org/licenses/by/4.0/',
          target: '_blank',
        },
      ],
    };
  },
};
</script>

<style scoped>
/* Add any additional footer styling here if needed */
</style>
