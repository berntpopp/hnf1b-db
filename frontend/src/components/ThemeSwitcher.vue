<template>
  <v-btn icon :aria-label="ariaLabel" variant="text" @click="toggle">
    <v-icon>{{ activeIcon }}</v-icon>
    <v-tooltip activator="parent" location="bottom">
      {{ ariaLabel }}
    </v-tooltip>
  </v-btn>
</template>

<script setup>
import { computed } from 'vue';
import { useAppTheme } from '@/composables/useAppTheme';

// Click-only toggle. One tap flips light ↔ dark. No menu — the
// 3-way preference (light / dark / system) is still supported in
// useAppTheme, it just isn't exposed in the toolbar to keep things
// minimal. System-follow can be chosen by code or future settings
// page; the default for a fresh user is explicit light.
const { resolvedTheme, toggle } = useAppTheme();

const activeIcon = computed(() =>
  resolvedTheme.value === 'dark' ? 'mdi-weather-night' : 'mdi-weather-sunny'
);

const ariaLabel = computed(() =>
  resolvedTheme.value === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
);
</script>
