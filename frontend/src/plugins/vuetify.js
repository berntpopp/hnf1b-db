// src/plugins/vuetify.js
// Framework documentation: https://vuetifyjs.com/

import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';
import { aliases, mdi } from 'vuetify/iconsets/mdi';

// Current Teal Theme
// Primary: #009688 (Teal)
// Secondary: #37474F (Slate)
// Accent: #FF8A65 (Soft Coral)
const hnf1bTheme = {
  dark: false,
  colors: {
    background: '#F5F7FA', // Soft off-white for depth
    surface: '#FFFFFF',
    primary: '#009688', // Maintaining established brand Teal
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
