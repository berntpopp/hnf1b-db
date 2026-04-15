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
// reads the same key and applies `hnf1b-theme--<light|dark>` class +
// `color-scheme` style to <html> before Vue mounts so there is no
// flash of wrong theme. (The `v-theme--<name>` class is added by
// Vuetify itself once the .v-application root mounts.)
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

// Dark theme — follows Material Design 3's "layered darkness" guidance.
// Rather than pure black, the palette uses a series of slightly lighter
// neutral tones so elevation and hierarchy can be communicated through
// tone shifts (since drop shadows are barely visible on black). Base
// #121212 is the MD3 canonical dark surface; elevated surfaces get a
// few percent lighter each step (+1..+5 dp) simulated via solid colors
// here to avoid the overhead of runtime overlay composition.
//
// References:
//   https://m3.material.io/styles/elevation/applying-elevation
//   https://material.io/design/color/dark-theme.html
const hnf1bThemeDark = {
  dark: true,
  colors: {
    // Canvas behind everything — MD3 canonical dark surface.
    background: '#121212',
    // Elevation 1dp — cards, sheets at rest.
    surface: '#1E1E1E',
    // Elevation 3dp — hovered cards, menus.
    'surface-bright': '#2A2A2A',
    // Elevation 2dp — secondary containers (e.g. toolbars inside cards).
    'surface-light': '#242424',
    // Elevation 5dp — dialogs, menus floating over content.
    'surface-variant': '#2F2F2F',
    // Muted text / icons for on-surface-variant tones.
    'on-surface-variant': '#C7C7C7',
    // Desaturated teal keeps the brand but passes AA on #1E1E1E
    // (contrast ratio ≈ 4.9 for large text against surface).
    primary: '#4DB6AC',
    'primary-darken-1': '#00897B',
    secondary: '#B0BEC5',
    'secondary-darken-1': '#78909C',
    accent: '#FFAB91',
    // MD3 error-container-on-dark, softer than pure red.
    error: '#F2B8B5',
    info: '#90CAF9',
    success: '#A5D6A7',
    warning: '#FFCC80',
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
