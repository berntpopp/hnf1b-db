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
        router.push({ name: 'Login' });
        return;
      }
      try {
        const response = await getCurrentUser(token);
        user.value = response.data;
        console.log('User info:', user.value);
      } catch (err) {
        console.error('Error fetching user info:', err);
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
