<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-lock-check</v-icon>
            <div>Reset Password</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Password reset successful. Redirecting to login...
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <v-form v-if="!success" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="newPassword"
                label="New Password"
                type="password"
                prepend-inner-icon="mdi-lock"
                :rules="[rules.required, rules.minLength]"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="confirmPassword"
                label="Confirm Password"
                type="password"
                prepend-inner-icon="mdi-lock-check"
                :rules="[rules.required, rules.match]"
                density="compact"
                class="mb-3"
              />
              <v-btn
                type="submit"
                color="primary"
                block
                :loading="loading"
                :disabled="!newPassword || !confirmPassword"
              >
                Reset Password
              </v-btn>
            </v-form>

            <div class="text-center mt-4">
              <router-link to="/forgot-password" class="text-decoration-none">
                Request a new reset link
              </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { confirmPasswordReset } from '@/api';

const route = useRoute();
const router = useRouter();

const newPassword = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const rules = {
  required: (v) => !!v || 'Required',
  minLength: (v) => (v && v.length >= 8) || 'Minimum 8 characters',
  match: (v) => v === newPassword.value || 'Passwords do not match',
};

async function handleSubmit() {
  if (newPassword.value !== confirmPassword.value) return;

  loading.value = true;
  error.value = '';
  try {
    await confirmPasswordReset(route.params.token, newPassword.value);
    success.value = true;
    setTimeout(() => router.push('/login'), 2000);
  } catch (err) {
    const detail = err.response?.data?.detail || 'Reset failed. The link may have expired.';
    error.value = detail;
    window.logService?.error('Password reset confirm failed', { error: detail });
  } finally {
    loading.value = false;
  }
}
</script>
