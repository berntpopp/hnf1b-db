<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-lock-reset</v-icon>
            <div>Forgot Password</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="submitted" type="info" variant="tonal" class="mb-4">
              If an account exists with that email, a reset link has been sent.
            </v-alert>

            <v-alert
              v-if="isDev && devToken"
              type="warning"
              variant="tonal"
              class="mb-4"
              title="Dev-only: Reset Token"
            >
              <a :href="resetUrl" class="text-break">{{ resetUrl }}</a>
            </v-alert>

            <v-form v-if="!submitted" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="email"
                label="Email address"
                type="email"
                prepend-inner-icon="mdi-email"
                :rules="[rules.required, rules.email]"
                density="compact"
                class="mb-3"
              />
              <v-btn type="submit" color="primary" block :loading="loading" :disabled="!email">
                Send Reset Link
              </v-btn>
            </v-form>

            <div class="text-center mt-4">
              <router-link to="/login" class="text-decoration-none"> Back to Login </router-link>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed } from 'vue';
import { requestPasswordReset } from '@/api';

const email = ref('');
const loading = ref(false);
const submitted = ref(false);
const devToken = ref(null);
const isDev = import.meta.env.DEV;

const resetUrl = computed(() =>
  devToken.value ? `${window.location.origin}/reset-password/${devToken.value}` : ''
);

const rules = {
  required: (v) => !!v || 'Required',
  email: (v) => /.+@.+\..+/.test(v) || 'Invalid email',
};

async function handleSubmit() {
  loading.value = true;
  try {
    const response = await requestPasswordReset(email.value);
    submitted.value = true;
    if (response.data.token) {
      devToken.value = response.data.token;
    }
  } catch (err) {
    // Still show "sent" message for anti-enumeration
    submitted.value = true;
    window.logService?.error('Password reset request failed', { error: err.message });
  } finally {
    loading.value = false;
  }
}
</script>
