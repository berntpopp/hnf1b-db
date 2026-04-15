// src/plugins/vuetify.js
// Framework documentation: https://vuetifyjs.com/
//
// Theme strategy
// ──────────────
// Two themes are registered: `hnf1bTheme` (light, brand default) and
// `hnf1bThemeDark` (dark, adjusted for accessibility while keeping the
// brand teal). A user's preference — 'light' | 'dark' | 'system' — is
// persisted to localStorage under `hnf1b-theme`. The key is read below
// to pick a `defaultTheme`; a small boot script in index.html also
// reads the same key and applies `v-theme--<name>` + `color-scheme` to
// <html> before Vue mounts so there is no flash of wrong theme.
//
// When the value is `'system'`, we resolve it once at module-evaluation
// time via `matchMedia('(prefers-color-scheme: dark)')`. Runtime system
// preference changes are handled by `useAppTheme()` (composable), which
// watches the media query and re-applies the resolved theme.

import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';
import { aliases, mdi } from 'vuetify/iconsets/mdi';

export const THEME_STORAGE_KEY = 'hnf1b-theme';
// Use Vuetify's canonical 'light' / 'dark' theme names rather than
// branded ones. Some Vuetify components (and the `useTheme()` helpers
// in the docs) default to looking up themes by these names, so using
// them avoids `theme.dark undefined` lookups from downstream code.
export const LIGHT_THEME = 'light';
export const DARK_THEME = 'dark';

// Light theme — current production palette.
// Primary: #009688 (Teal)
// Secondary: #37474F (Slate)
// Accent: #FF8A65 (Soft Coral)
const hnf1bTheme = {
  dark: false,
  colors: {
    background: '#F5F7FA', // Soft off-white for depth
    surface: '#FFFFFF',
    primary: '#009688',
    'primary-darken-1': '#00796B',
    secondary: '#37474F',
    'secondary-darken-1': '#263238',
    accent: '#FF8A65',
    error: '#B00020',
    info: '#2196F3',
    success: '#4CAF50',
    warning: '#FB8C00',
  },
};

// Dark theme — desaturated background, lifted teal accent for AA
// contrast against dark surfaces. Mirrors Material Design 3's on-dark
// guidance without dropping the brand identity.
const hnf1bThemeDark = {
  dark: true,
  colors: {
    background: '#0F1416',
    surface: '#1A2124',
    'surface-bright': '#242B2E',
    'surface-light': '#2A3235',
    'surface-variant': '#3A4246',
    'on-surface-variant': '#C7CFD3',
    primary: '#4DB6AC', // Lightened teal for contrast on dark
    'primary-darken-1': '#00897B',
    secondary: '#90A4AE',
    'secondary-darken-1': '#607D8B',
    accent: '#FFAB91',
    error: '#CF6679',
    info: '#64B5F6',
    success: '#81C784',
    warning: '#FFB74D',
  },
};

// Resolve an initial theme name before Vue mounts. Reads localStorage
// (set by the boot script in index.html and by useAppTheme), falling
// back to the OS preference when the stored value is 'system' or
// missing.
function resolveInitialTheme() {
  if (typeof window === 'undefined') return LIGHT_THEME;

  const stored = window.localStorage?.getItem(THEME_STORAGE_KEY);
  if (stored === LIGHT_THEME || stored === 'light') return LIGHT_THEME;
  if (stored === DARK_THEME || stored === 'dark') return DARK_THEME;

  // `'system'` or unset → follow the OS.
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  return prefersDark ? DARK_THEME : LIGHT_THEME;
}

export default createVuetify({
  theme: {
    defaultTheme: resolveInitialTheme(),
    themes: {
      [LIGHT_THEME]: hnf1bTheme,
      [DARK_THEME]: hnf1bThemeDark,
    },
  },
  defaults: {
    VCard: {
      rounded: 'lg',
      elevation: 2, // Default subtle lift
    },
    VBtn: {
      rounded: 'md',
      fontWeight: '600',
      letterSpacing: '0',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
    },
  },
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
});
