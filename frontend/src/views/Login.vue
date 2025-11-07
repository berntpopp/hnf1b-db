<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <v-card-title class="text-h5"> Login </v-card-title>
          <v-card-text>
            <v-form ref="loginForm" @submit.prevent="handleLogin">
              <v-text-field
                v-model="username"
                label="Username"
                :disabled="authStore.isLoading"
                required
              />
              <v-text-field
                v-model="password"
                label="Password"
                type="password"
                :disabled="authStore.isLoading"
                required
              />
              <v-btn
                type="submit"
                color="teal"
                class="mt-4"
                :loading="authStore.isLoading"
                :disabled="!username || !password"
              >
                Login
              </v-btn>
            </v-form>
            <v-alert v-if="authStore.error" type="error" class="mt-4">
              {{ authStore.error }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const username = ref('');
const password = ref('');

/**
 * Handles the login process using the Pinia auth store.
 */
const handleLogin = async () => {
  try {
    const success = await authStore.login({
      username: username.value,
      password: password.value,
    });

    if (success) {
      // Redirect to original destination or user profile page
      const redirectPath = route.query.redirect || '/user';
      router.push(redirectPath);
    }
  } catch (err) {
    // Error is already handled by the auth store
    window.logService.warn('Login failed', {
      error: err.message,
    });
  }
};
</script>
