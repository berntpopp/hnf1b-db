<template>
  <v-card class="mt-4" variant="tonal" color="warning">
    <v-card-title class="text-caption"> DEV MODE — not available in production </v-card-title>
    <v-card-text>
      <v-btn
        v-for="u in fixtureUsers"
        :key="u.username"
        class="mr-2 mb-2"
        color="primary"
        variant="outlined"
        :loading="loadingUser === u.username"
        @click="onClick(u.username)"
      >
        Log in as {{ u.label }}
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();

const fixtureUsers = [
  { username: 'dev-admin', label: 'admin' },
  { username: 'dev-curator', label: 'curator' },
  { username: 'dev-viewer', label: 'viewer' },
];

const loadingUser = ref(null);

async function onClick(username) {
  loadingUser.value = username;
  try {
    await authStore.devLoginAs(username);
  } catch (err) {
    window.logService.error('dev login failed', { username, error: err.message });
  } finally {
    loadingUser.value = null;
  }
}
</script>
