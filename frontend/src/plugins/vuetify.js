// src/plugins/vuetify.js
// Framework documentation: https://vuetifyjs.com/
//
// Theme colors are imported from designTokens.js for single source of truth.
// See: frontend/src/utils/designTokens.js

import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';
import { aliases, mdi } from 'vuetify/iconsets/mdi';
import { COLORS } from '@/utils/designTokens';

// HNF1B Database Theme
// Colors imported from designTokens.js:
// - Primary: Teal (#009688)
// - Secondary: Slate (#37474F)
// - Accent: Gold/Amber (#FFB300) - changed from coral for better harmony
const hnf1bTheme = {
  dark: false,
  colors: {
    background: COLORS.BACKGROUND,
    surface: COLORS.SURFACE,
    primary: COLORS.PRIMARY,
    'primary-darken-1': COLORS.PRIMARY_DARKEN_1,
    secondary: COLORS.SECONDARY,
    'secondary-darken-1': COLORS.SECONDARY_DARKEN_1,
    accent: COLORS.ACCENT,
    error: COLORS.ERROR,
    info: COLORS.INFO,
    success: COLORS.SUCCESS,
    warning: COLORS.WARNING,
  },
};

export default createVuetify({
  theme: {
    defaultTheme: 'hnf1bTheme',
    themes: {
      hnf1bTheme,
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
