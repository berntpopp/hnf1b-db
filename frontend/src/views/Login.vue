<template>
  <v-container class="fill-height">
    <v-row justify="center" align="center">
      <v-col cols="12" sm="8" md="6" lg="4">
        <!-- Login Card -->
        <v-card elevation="8" rounded="lg" class="pa-2">
          <!-- Header -->
          <v-card-title class="text-h4 font-weight-bold text-center py-6">
            Welcome Back
          </v-card-title>

          <v-card-subtitle class="text-center pb-4">
            Sign in to access the HNF1B Database
          </v-card-subtitle>

          <v-card-text>
            <!-- Error Alert -->
            <v-alert
              v-if="authStore.error"
              type="error"
              variant="tonal"
              closable
              class="mb-4"
              @click:close="authStore.error = null"
            >
              <div class="text-subtitle-2">{{ authStore.error }}</div>
              <div class="text-caption mt-1">Please check your credentials and try again.</div>
            </v-alert>

            <!-- Login Form -->
            <v-form ref="loginForm" @submit.prevent="handleLogin">
              <!-- Username Field -->
              <v-text-field
                v-model="username"
                label="Username"
                prepend-inner-icon="mdi-account"
                variant="outlined"
                density="comfortable"
                :disabled="authStore.isLoading"
                :rules="[rules.required]"
                autocomplete="username"
                autofocus
                class="mb-2"
              />

              <!-- Password Field -->
              <v-text-field
                v-model="password"
                label="Password"
                prepend-inner-icon="mdi-lock"
                :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
                :type="showPassword ? 'text' : 'password'"
                variant="outlined"
                density="comfortable"
                :disabled="authStore.isLoading"
                :rules="[rules.required]"
                autocomplete="current-password"
                class="mb-2"
                @click:append-inner="showPassword = !showPassword"
              />

              <!-- Remember Me & Forgot Password -->
              <div class="d-flex justify-space-between align-center mb-4">
                <v-checkbox
                  v-model="rememberMe"
                  label="Remember me"
                  density="compact"
                  hide-details
                  color="teal"
                />
                <v-btn
                  variant="text"
                  color="teal"
                  size="small"
                  class="text-none"
                  @click="handleForgotPassword"
                >
                  Forgot password?
                </v-btn>
              </div>

              <!-- Login Button -->
              <v-btn
                type="submit"
                color="teal"
                variant="elevated"
                size="large"
                block
                :loading="authStore.isLoading"
                :disabled="!username || !password"
                class="text-none font-weight-bold"
              >
                <v-icon start>mdi-login</v-icon>
                Sign In
              </v-btn>
            </v-form>
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
const showPassword = ref(false);
const rememberMe = ref(false);

// Validation rules
const rules = {
  required: (value) => !!value || 'This field is required',
};

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
      // Save remember me preference
      if (rememberMe.value) {
        localStorage.setItem('remember_me', 'true');
        localStorage.setItem('remembered_username', username.value);
      } else {
        localStorage.removeItem('remember_me');
        localStorage.removeItem('remembered_username');
      }

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

/**
 * Handles forgot password action.
 */
const handleForgotPassword = () => {
  // TODO: Implement forgot password flow
  window.logService.info('Forgot password clicked');
  alert('Password reset functionality will be implemented in a future update.');
};

// Check if user should be remembered on mount
if (localStorage.getItem('remember_me') === 'true') {
  const rememberedUsername = localStorage.getItem('remembered_username');
  if (rememberedUsername) {
    username.value = rememberedUsername;
    rememberMe.value = true;
  }
}
</script>
