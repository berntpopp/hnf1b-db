<template>
  <v-menu location="bottom end" offset="8">
    <template #activator="{ props: activatorProps }">
      <v-btn icon :aria-label="activatorAriaLabel" variant="text" v-bind="activatorProps">
        <v-icon>{{ activeIcon }}</v-icon>
        <v-tooltip activator="parent" location="bottom">
          {{ activatorAriaLabel }}
        </v-tooltip>
      </v-btn>
    </template>

    <v-list density="compact" nav min-width="180">
      <v-list-item
        v-for="option in options"
        :key="option.value"
        :active="preference === option.value"
        :prepend-icon="option.icon"
        :title="option.label"
        @click="setPreference(option.value)"
      />
    </v-list>
  </v-menu>
</template>

<script setup>
import { computed } from 'vue';
import { useAppTheme } from '@/composables/useAppTheme';

// Three-way preference: explicit light, explicit dark, or follow the
// user's OS. Keeps parity with macOS / Windows / GNOME system
// switchers that also offer a three-way toggle.
const options = [
  { value: 'light', label: 'Light', icon: 'mdi-weather-sunny' },
  { value: 'dark', label: 'Dark', icon: 'mdi-weather-night' },
  { value: 'system', label: 'System', icon: 'mdi-theme-light-dark' },
];

const { preference, resolvedTheme, setPreference } = useAppTheme();

// Activator icon reflects what's ACTUALLY showing, not the raw
// preference — so if the user picks "System" and their OS is dark,
// the button shows a moon. Makes the toggle's next-action obvious.
const activeIcon = computed(() => {
  if (preference.value === 'system') return 'mdi-theme-light-dark';
  return resolvedTheme.value === 'dark' ? 'mdi-weather-night' : 'mdi-weather-sunny';
});

const activatorAriaLabel = computed(() => {
  const current =
    preference.value === 'system'
      ? `Theme: system (${resolvedTheme.value})`
      : `Theme: ${preference.value}`;
  return `${current} — change theme`;
});
</script>
