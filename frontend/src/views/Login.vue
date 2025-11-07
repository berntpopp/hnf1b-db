<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="6">
        <v-card class="pa-4">
          <v-card-title class="text-h5"> Login </v-card-title>
          <v-card-text>
            <v-form ref="loginForm" @submit.prevent="handleLogin">
              <v-text-field v-model="username" label="Username" required />
              <v-text-field v-model="password" label="Password" type="password" required />
              <v-btn type="submit" color="teal" class="mt-4"> Login </v-btn>
            </v-form>
            <v-alert v-if="error" type="error" class="mt-4">
              {{ error }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { login } from '@/api/auth';
import { setToken } from '@/utils/auth';

export default {
  name: 'Login',
  setup() {
    const username = ref('');
    const password = ref('');
    const error = ref('');
    const router = useRouter();

    /**
     * Handles the login process by calling the API and storing the token.
     */
    const handleLogin = async () => {
      error.value = '';
      try {
        const response = await login(username.value, password.value);
        if (response.data && response.data.access_token) {
          setToken(response.data.access_token);
          window.logService.info('User logged in successfully', {
            username: username.value,
          });
          router.push({ name: 'User' });
        } else {
          error.value = 'Invalid response from server.';
        }
      } catch (err) {
        window.logService.warn('Login attempt failed', {
          error: err.message,
          status: err.response?.status,
          username: username.value,
        });
        error.value = 'Login failed. Please check your credentials.';
      }
    };

    return {
      username,
      password,
      error,
      handleLogin,
    };
  },
};
</script>
