<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="8">
        <v-card class="pa-4">
          <v-card-title class="text-h5"> User Profile </v-card-title>
          <v-card-text>
            <div v-if="user">
              <p><strong>Username:</strong> {{ user.user }}</p>
              <!-- Additional user details can be displayed here -->
            </div>
            <v-alert v-else type="error"> Failed to load user information. </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { ref, onMounted } from 'vue';
import { getToken } from '@/utils/auth';
import { getCurrentUser } from '@/api/auth';
import { useRouter } from 'vue-router';

export default {
  name: 'User',
  setup() {
    const user = ref(null);
    const router = useRouter();

    /**
     * Fetches the current user's information from the API.
     */
    const fetchUser = async () => {
      const token = getToken();
      if (!token) {
        window.logService.warn('No auth token found, redirecting to login');
        router.push({ name: 'Login' });
        return;
      }
      try {
        const response = await getCurrentUser(token);
        user.value = response.data;
        window.logService.info('User profile loaded successfully', {
          username: user.value?.user,
        });
      } catch (err) {
        window.logService.error('Failed to fetch user info', {
          error: err.message,
          status: err.response?.status,
        });
        user.value = null;
      }
    };

    onMounted(fetchUser);

    return {
      user,
    };
  },
};
</script>
