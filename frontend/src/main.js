// src/main.js
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';
// Import app styles AFTER MDI to allow font-display override
import './style.css';

// Import logging services
import { logService } from '@/services/logService';
import { useLogStore } from '@/stores/logStore';
import { useAuthStore } from '@/stores/authStore';

const pinia = createPinia();
const vuetify = createVuetify();
const app = createApp(App);

app.use(pinia); // Pinia must be registered before router

// Initialize log service with Pinia store (after pinia.use)
const logStore = useLogStore();
logService.init(logStore);

// Initialize auth store and restore session if token exists
const authStore = useAuthStore();
authStore.initialize().catch((err) => {
  window.logService.warn('Failed to initialize auth session', {
    error: err.message,
  });
});

app.use(router);
app.use(vuetify);
app.mount('#app');
