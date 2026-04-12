<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="5" lg="4">
        <v-card elevation="4">
          <v-card-title class="text-center pt-6">
            <v-icon size="large" class="mb-2">mdi-account-plus</v-icon>
            <div>Accept Invite</div>
          </v-card-title>
          <v-card-text>
            <v-alert v-if="success" type="success" variant="tonal" class="mb-4">
              Account created! Redirecting to login...
            </v-alert>

            <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
              {{ error }}
            </v-alert>

            <div v-if="inviteEmail" class="text-caption text-grey mb-3">
              Invite for: <strong>{{ inviteEmail }}</strong>
            </div>

            <v-form v-if="!success" @submit.prevent="handleSubmit">
              <v-text-field
                v-model="username"
                label="Username"
                prepend-inner-icon="mdi-account"
                :rules="[rules.required, rules.minLength3]"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="fullName"
                label="Full Name"
                prepend-inner-icon="mdi-badge-account"
                density="compact"
                class="mb-3"
              />
              <v-text-field
                v-model="password"
                label="Password"
                type="password"
                prepend-inner-icon="mdi-lock"
                :rules="[rules.required, rules.minLength8]"
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
                :disabled="!username || !password || !confirmPassword"
              >
                Create Account
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { acceptInvite } from '@/api';

const route = useRoute();
const router = useRouter();

const username = ref('');
const fullName = ref('');
const password = ref('');
const confirmPassword = ref('');
const loading = ref(false);
const success = ref(false);
const error = ref('');

const inviteEmail = computed(() => route.query.email || '');

const rules = {
  required: (v) => !!v || 'Required',
  minLength3: (v) => (v && v.length >= 3) || 'Minimum 3 characters',
  minLength8: (v) => (v && v.length >= 8) || 'Minimum 8 characters',
  match: (v) => v === password.value || 'Passwords do not match',
};

async function handleSubmit() {
  if (password.value !== confirmPassword.value) return;

  loading.value = true;
  error.value = '';
  try {
    await acceptInvite(route.params.token, username.value, password.value, fullName.value);
    success.value = true;
    setTimeout(() => router.push('/login'), 2000);
  } catch (err) {
    const detail = err.response?.data?.detail || 'Failed to accept invite.';
    error.value = detail;
    window.logService?.error('Invite accept failed', { error: detail });
  } finally {
    loading.value = false;
  }
}
</script>
