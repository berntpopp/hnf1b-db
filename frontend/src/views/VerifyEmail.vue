<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-email-check</v-icon>
            <div>Email Verification</div>
          </v-card-title>
          <v-card-text class="text-center">
            <v-progress-circular v-if="loading" indeterminate color="primary" class="mb-4" />

            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Email verified successfully!
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <div class="mt-4">
              <router-link to="/login" class="text-decoration-none"> Go to Login </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { verifyEmail } from '@/api';

const route = useRoute();

const loading = ref(true);
const success = ref(false);
const error = ref('');

onMounted(async () => {
  try {
    await verifyEmail(route.params.token);
    success.value = true;
  } catch (err) {
    const detail = err.response?.data?.detail || 'Verification failed. The link may have expired.';
    error.value = detail;
    window.logService?.error('Email verification failed', { error: detail });
  } finally {
    loading.value = false;
  }
});
</script>
