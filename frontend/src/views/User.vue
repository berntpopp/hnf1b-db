<template>
  <v-container class="py-6">
    <v-row>
      <!-- Profile Header -->
      <v-col cols="12">
        <v-card elevation="2" rounded="lg">
          <v-card-text class="pa-6">
            <div class="d-flex flex-column flex-sm-row align-center gap-4">
              <!-- Avatar -->
              <v-avatar :color="getRoleColor(authStore.user?.role)" size="96">
                <span class="text-h3 font-weight-bold text-white">
                  {{ getUserInitials }}
                </span>
              </v-avatar>

              <!-- User Info -->
              <div class="flex-grow-1 text-center text-sm-start">
                <h1 class="text-h4 font-weight-bold mb-2">
                  {{ authStore.user?.full_name || authStore.user?.username }}
                </h1>
                <div class="d-flex flex-wrap gap-2 justify-center justify-sm-start">
                  <v-chip
                    :color="getRoleColor(authStore.user?.role)"
                    variant="flat"
                    prepend-icon="mdi-shield-account"
                  >
                    {{ authStore.user?.role }}
                  </v-chip>
                  <v-chip
                    v-if="authStore.user?.is_active"
                    color="success"
                    variant="tonal"
                    prepend-icon="mdi-check-circle"
                  >
                    Active
                  </v-chip>
                  <v-chip
                    v-if="authStore.user?.is_verified"
                    color="info"
                    variant="tonal"
                    prepend-icon="mdi-check-decagram"
                  >
                    Verified
                  </v-chip>
                </div>
              </div>

              <!-- Quick Actions -->
              <div class="d-flex flex-column gap-2">
                <v-btn
                  color="primary"
                  variant="elevated"
                  prepend-icon="mdi-lock-reset"
                  @click="showPasswordDialog = true"
                >
                  Change Password
                </v-btn>
                <v-btn
                  color="error"
                  variant="outlined"
                  prepend-icon="mdi-logout"
                  @click="handleLogout"
                >
                  Logout
                </v-btn>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Personal Information Section -->
      <v-col cols="12" md="6">
        <v-card elevation="2" rounded="lg" class="h-100">
          <v-card-title class="d-flex align-center pa-4 bg-surface-variant">
            <v-icon start color="primary">mdi-account-circle</v-icon>
            <span class="text-h6">Personal Information</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <v-list lines="two" class="pa-0">
              <v-list-item class="px-0">
                <template #prepend>
                  <v-icon>mdi-account</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Username
                </v-list-item-title>
                <v-list-item-subtitle class="text-body-1 font-weight-medium">
                  {{ authStore.user?.username }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item class="px-0">
                <template #prepend>
                  <v-icon>mdi-email</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Email Address
                </v-list-item-title>
                <v-list-item-subtitle class="text-body-1 font-weight-medium">
                  {{ authStore.user?.email }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item v-if="authStore.user?.full_name" class="px-0">
                <template #prepend>
                  <v-icon>mdi-card-account-details</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Full Name
                </v-list-item-title>
                <v-list-item-subtitle class="text-body-1 font-weight-medium">
                  {{ authStore.user?.full_name }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Account Security Section -->
      <v-col cols="12" md="6">
        <v-card elevation="2" rounded="lg" class="h-100">
          <v-card-title class="d-flex align-center pa-4 bg-surface-variant">
            <v-icon start color="success">mdi-shield-check</v-icon>
            <span class="text-h6">Account Security</span>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <v-list lines="two" class="pa-0">
              <v-list-item class="px-0">
                <template #prepend>
                  <v-icon>mdi-shield-star</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Role & Access Level
                </v-list-item-title>
                <v-list-item-subtitle>
                  <v-chip :color="getRoleColor(authStore.user?.role)" size="small" class="mt-1">
                    {{ authStore.user?.role }}
                  </v-chip>
                  <span v-if="authStore.isAdmin" class="ml-2">
                    <v-icon size="small" color="error">mdi-crown</v-icon>
                    Full Administrator Access
                  </span>
                  <span v-else-if="authStore.isCurator" class="ml-2">
                    <v-icon size="small" color="warning">mdi-pencil</v-icon>
                    Curator Access
                  </span>
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item class="px-0">
                <template #prepend>
                  <v-icon>mdi-clock-outline</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Last Login
                </v-list-item-title>
                <v-list-item-subtitle class="text-body-1 font-weight-medium">
                  {{ formatDate(authStore.user?.last_login) }}
                </v-list-item-subtitle>
              </v-list-item>

              <v-list-item class="px-0">
                <template #prepend>
                  <v-icon>mdi-account-check</v-icon>
                </template>
                <v-list-item-title class="text-subtitle-2 text-medium-emphasis">
                  Account Status
                </v-list-item-title>
                <v-list-item-subtitle>
                  <div class="d-flex gap-2 mt-1">
                    <v-chip
                      :color="authStore.user?.is_active ? 'success' : 'error'"
                      size="small"
                      variant="flat"
                    >
                      {{ authStore.user?.is_active ? 'Active' : 'Inactive' }}
                    </v-chip>
                    <v-chip
                      v-if="authStore.user?.is_verified"
                      color="info"
                      size="small"
                      variant="flat"
                    >
                      Verified
                    </v-chip>
                  </div>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Permissions & Access Section -->
      <v-col cols="12">
        <v-card elevation="2" rounded="lg">
          <v-card-title class="d-flex align-center pa-4 bg-surface-variant">
            <v-icon start color="warning">mdi-key-variant</v-icon>
            <span class="text-h6">Permissions & Access Rights</span>
            <v-spacer />
            <v-chip size="small" variant="tonal">
              {{ authStore.userPermissions.length }} permissions
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-card-text class="pa-4">
            <!-- Permission Categories -->
            <div v-for="category in permissionCategories" :key="category.name" class="mb-4">
              <div class="d-flex align-center mb-2">
                <v-icon :color="category.color" size="small" class="mr-2">
                  {{ category.icon }}
                </v-icon>
                <span class="text-subtitle-1 font-weight-bold">{{ category.name }}</span>
                <v-chip size="x-small" class="ml-2" variant="tonal">
                  {{ category.permissions.length }}
                </v-chip>
              </div>
              <div class="d-flex flex-wrap gap-2">
                <v-chip
                  v-for="permission in category.permissions"
                  :key="permission"
                  size="small"
                  variant="outlined"
                  :color="category.color"
                >
                  {{ permission }}
                </v-chip>
              </div>
            </div>

            <!-- Empty State -->
            <v-alert v-if="authStore.userPermissions.length === 0" type="info" variant="tonal">
              <div class="text-subtitle-2">No permissions assigned</div>
              <div class="text-caption">Contact an administrator to request access.</div>
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Change Password Dialog -->
    <v-dialog v-model="showPasswordDialog" max-width="500" persistent>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pa-4 bg-surface-variant">
          <v-icon start color="primary">mdi-lock-reset</v-icon>
          <span class="text-h6">Change Password</span>
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-form ref="passwordForm" @submit.prevent="handlePasswordChange">
            <v-text-field
              v-model="currentPassword"
              label="Current Password"
              prepend-inner-icon="mdi-lock"
              :append-inner-icon="showCurrentPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showCurrentPassword ? 'text' : 'password'"
              variant="outlined"
              density="comfortable"
              :disabled="authStore.isLoading"
              autocomplete="current-password"
              class="mb-2"
              @click:append-inner="showCurrentPassword = !showCurrentPassword"
            />
            <v-text-field
              v-model="newPassword"
              label="New Password"
              prepend-inner-icon="mdi-lock-plus"
              :append-inner-icon="showNewPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showNewPassword ? 'text' : 'password'"
              variant="outlined"
              density="comfortable"
              :disabled="authStore.isLoading"
              autocomplete="new-password"
              hint="Minimum 8 characters"
              persistent-hint
              class="mb-2"
              @click:append-inner="showNewPassword = !showNewPassword"
            />
            <v-text-field
              v-model="confirmPassword"
              label="Confirm New Password"
              prepend-inner-icon="mdi-lock-check"
              :append-inner-icon="showConfirmPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :type="showConfirmPassword ? 'text' : 'password'"
              variant="outlined"
              density="comfortable"
              :disabled="authStore.isLoading"
              autocomplete="new-password"
              :error="newPassword !== confirmPassword && confirmPassword.length > 0"
              :error-messages="
                newPassword !== confirmPassword && confirmPassword.length > 0
                  ? ['Passwords do not match']
                  : []
              "
              class="mb-2"
              @click:append-inner="showConfirmPassword = !showConfirmPassword"
            />
          </v-form>

          <v-alert v-if="passwordError" type="error" variant="tonal" class="mt-2" closable>
            {{ passwordError }}
          </v-alert>
          <v-alert v-if="passwordSuccess" type="success" variant="tonal" class="mt-2">
            <v-icon start>mdi-check-circle</v-icon>
            {{ passwordSuccess }}
          </v-alert>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="text" @click="closePasswordDialog">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="elevated"
            :loading="authStore.isLoading"
            :disabled="!currentPassword || !newPassword || !confirmPassword"
            @click="handlePasswordChange"
          >
            Change Password
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const showPasswordDialog = ref(false);
const currentPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);
const passwordError = ref('');
const passwordSuccess = ref('');

/**
 * Get user initials for avatar
 */
const getUserInitials = computed(() => {
  if (!authStore.user?.username) return '?';
  const name = authStore.user.full_name || authStore.user.username;
  const parts = name.split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
});

/**
 * Get role badge color
 */
const getRoleColor = (role) => {
  const colors = {
    admin: 'error',
    curator: 'warning',
    viewer: 'info',
  };
  return colors[role] || 'grey';
};

/**
 * Format date for display
 */
const formatDate = (dateString) => {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * Categorize permissions for better display
 */
const permissionCategories = computed(() => {
  const permissions = authStore.userPermissions || [];

  const categories = {
    users: {
      name: 'User Management',
      icon: 'mdi-account-group',
      color: 'blue',
      permissions: [],
    },
    phenopackets: {
      name: 'Phenopackets',
      icon: 'mdi-file-document',
      color: 'green',
      permissions: [],
    },
    variants: {
      name: 'Variants',
      icon: 'mdi-dna',
      color: 'purple',
      permissions: [],
    },
    system: {
      name: 'System & Administration',
      icon: 'mdi-cog',
      color: 'orange',
      permissions: [],
    },
  };

  permissions.forEach((permission) => {
    if (permission.startsWith('users:')) {
      categories.users.permissions.push(permission);
    } else if (permission.startsWith('phenopackets:')) {
      categories.phenopackets.permissions.push(permission);
    } else if (permission.startsWith('variants:')) {
      categories.variants.permissions.push(permission);
    } else {
      categories.system.permissions.push(permission);
    }
  });

  // Return only categories with permissions
  return Object.values(categories).filter((cat) => cat.permissions.length > 0);
});

/**
 * Handle password change
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
 * Close password dialog and reset form
 */
const closePasswordDialog = () => {
  showPasswordDialog.value = false;
  currentPassword.value = '';
  newPassword.value = '';
  confirmPassword.value = '';
  showCurrentPassword.value = false;
  showNewPassword.value = false;
  showConfirmPassword.value = false;
  passwordError.value = '';
  passwordSuccess.value = '';
};

/**
 * Handle logout
 */
const handleLogout = async () => {
  await authStore.logout();
  router.push('/');
};

/**
 * Initialize user data on mount
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

<style scoped>
.h-100 {
  height: 100%;
}
</style>
