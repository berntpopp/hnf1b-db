<template>
  <v-container>
    <v-row justify="center">
      <v-col cols="12" md="8">
        <v-card class="pa-4">
          <v-card-title class="text-h5 d-flex align-center justify-space-between">
            <span>User Profile</span>
            <v-chip v-if="authStore.user" :color="getRoleColor(authStore.user.role)" dark>
              {{ authStore.user.role }}
            </v-chip>
          </v-card-title>

          <v-card-text>
            <v-progress-circular v-if="authStore.isLoading" indeterminate color="teal" />

            <div v-else-if="authStore.user" class="user-details">
              <v-list>
                <v-list-item>
                  <v-list-item-title>Username</v-list-item-title>
                  <v-list-item-subtitle>{{ authStore.user.username }}</v-list-item-subtitle>
                </v-list-item>

                <v-list-item>
                  <v-list-item-title>Email</v-list-item-title>
                  <v-list-item-subtitle>{{ authStore.user.email }}</v-list-item-subtitle>
                </v-list-item>

                <v-list-item v-if="authStore.user.full_name">
                  <v-list-item-title>Full Name</v-list-item-title>
                  <v-list-item-subtitle>{{ authStore.user.full_name }}</v-list-item-subtitle>
                </v-list-item>

                <v-list-item>
                  <v-list-item-title>Role</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ authStore.user.role }}
                    <v-chip v-if="authStore.isAdmin" color="red" size="small" class="ml-2">
                      Admin
                    </v-chip>
                    <v-chip
                      v-else-if="authStore.isCurator"
                      color="orange"
                      size="small"
                      class="ml-2"
                    >
                      Curator
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item>

                <v-list-item>
                  <v-list-item-title>Account Status</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip :color="authStore.user.is_active ? 'green' : 'red'" size="small">
                      {{ authStore.user.is_active ? 'Active' : 'Inactive' }}
                    </v-chip>
                    <v-chip
                      v-if="authStore.user.is_verified"
                      color="blue"
                      size="small"
                      class="ml-2"
                    >
                      Verified
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item>

                <v-list-item v-if="authStore.user.last_login">
                  <v-list-item-title>Last Login</v-list-item-title>
                  <v-list-item-subtitle>
                    {{ formatDate(authStore.user.last_login) }}
                  </v-list-item-subtitle>
                </v-list-item>

                <v-list-item>
                  <v-list-item-title>Permissions</v-list-item-title>
                  <v-list-item-subtitle>
                    <v-chip
                      v-for="permission in authStore.userPermissions"
                      :key="permission"
                      size="small"
                      class="mr-1 mt-1"
                    >
                      {{ permission }}
                    </v-chip>
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list>

              <v-divider class="my-4" />

              <div class="d-flex justify-end gap-2">
                <v-btn color="primary" @click="showPasswordDialog = true"> Change Password </v-btn>
                <v-btn color="error" @click="handleLogout"> Logout </v-btn>
              </div>
            </div>

            <v-alert v-else type="error"> Failed to load user information. </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Password Change Dialog -->
    <v-dialog v-model="showPasswordDialog" max-width="500">
      <v-card>
        <v-card-title>Change Password</v-card-title>
        <v-card-text>
          <v-form ref="passwordForm" @submit.prevent="handlePasswordChange">
            <v-text-field
              v-model="currentPassword"
              label="Current Password"
              type="password"
              :disabled="authStore.isLoading"
              required
            />
            <v-text-field
              v-model="newPassword"
              label="New Password"
              type="password"
              :disabled="authStore.isLoading"
              required
            />
            <v-text-field
              v-model="confirmPassword"
              label="Confirm New Password"
              type="password"
              :disabled="authStore.isLoading"
              required
            />
          </v-form>
          <v-alert v-if="passwordError" type="error" class="mt-2">
            {{ passwordError }}
          </v-alert>
          <v-alert v-if="passwordSuccess" type="success" class="mt-2">
            {{ passwordSuccess }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn text @click="closePasswordDialog">Cancel</v-btn>
          <v-btn color="primary" :loading="authStore.isLoading" @click="handlePasswordChange">
            Change Password
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const showPasswordDialog = ref(false);
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const passwordError = ref('');
const passwordSuccess = ref('');

/**
 * Get role badge color based on role name.
 */
const getRoleColor = (role) => {
  const colors = {
    admin: 'red',
    curator: 'orange',
    viewer: 'grey',
  };
  return colors[role] || 'grey';
};

/**
 * Format date for display.
 */
const formatDate = (dateString) => {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  return date.toLocaleString();
};

/**
 * Handle password change.
 */
const handlePasswordChange = async () => {
  passwordError.value = '';
  passwordSuccess.value = '';

  // Validate passwords match
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'New passwords do not match';
    return;
  }

  // Validate password strength
  if (newPassword.value.length < 8) {
    passwordError.value = 'Password must be at least 8 characters';
    return;
  }

  try {
    await authStore.changePassword(currentPassword.value, newPassword.value);
    passwordSuccess.value = 'Password changed successfully';

    // Clear form and close dialog after 2 seconds
    setTimeout(() => {
      closePasswordDialog();
    }, 2000);
  } catch {
    passwordError.value = authStore.error || 'Failed to change password';
  }
};

/**
 * Close password dialog and reset form.
 */
const closePasswordDialog = () => {
  showPasswordDialog.value = false;
  currentPassword.value = '';
  newPassword.value = '';
  confirmPassword.value = '';
  passwordError.value = '';
  passwordSuccess.value = '';
};

/**
 * Handle logout.
 */
const handleLogout = async () => {
  await authStore.logout();
  router.push({ name: 'Login' });
};

/**
 * Initialize user data on mount.
 */
onMounted(async () => {
  // If not authenticated, redirect to login
  if (!authStore.isAuthenticated) {
    window.logService.warn('User not authenticated, redirecting to login');
    router.push({ name: 'Login' });
    return;
  }

  // If user data not loaded, fetch it
  if (!authStore.user) {
    try {
      await authStore.fetchCurrentUser();
    } catch (err) {
      window.logService.error('Failed to fetch user info', {
        error: err.message,
      });
      router.push({ name: 'Login' });
    }
  }
});
</script>
