// src/main.js
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { createVuetify } from 'vuetify';
import 'vuetify/styles';
import '@mdi/font/css/materialdesignicons.css';

// Import logging services
import { logService } from '@/services/logService';
import { useLogStore } from '@/stores/logStore';

const pinia = createPinia();
const vuetify = createVuetify();
const app = createApp(App);

app.use(pinia); // Pinia must be registered before router

// Initialize log service with Pinia store (after pinia.use)
const logStore = useLogStore();
logService.init(logStore);

app.use(router);
app.use(vuetify);
app.mount('#app');
