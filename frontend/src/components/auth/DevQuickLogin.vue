<template>
  <v-card class="mt-4" variant="tonal" color="warning">
    <v-card-title class="text-caption"> DEV QUICK LOGIN — local development only </v-card-title>
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
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const fixtureUsers = [
  { username: 'dev-admin', label: 'admin' },
  { username: 'dev-curator', label: 'curator' },
  { username: 'dev-viewer', label: 'viewer' },
];

const loadingUser = ref(null);

// Only treat relative in-app paths as valid redirect targets to avoid
// open-redirect bounces. Also refuse to land back on an auth-adjacent
// page so the user never "returns" to a login/reset form after signing in.
function resolveRedirect(rawRedirect) {
  if (typeof rawRedirect !== 'string') return '/user';
  if (!rawRedirect.startsWith('/') || rawRedirect.startsWith('//')) return '/user';
  if (
    /^\/(login|forgot-password|reset-password|accept-invite|verify-email)(\/|$|\?)/.test(
      rawRedirect
    )
  ) {
    return '/user';
  }
  return rawRedirect;
}

async function onClick(username) {
  loadingUser.value = username;
  try {
    await authStore.devLoginAs(username);
    router.push(resolveRedirect(route.query.redirect));
  } catch (err) {
    window.logService.error('dev login failed', { username, error: err.message });
  } finally {
    loadingUser.value = null;
  }
}
</script>
