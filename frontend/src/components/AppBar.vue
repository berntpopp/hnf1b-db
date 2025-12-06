<template>
  <v-app-bar app color="teal" dark elevation="2" style="z-index: 1009">
    <v-container fluid class="d-flex align-center px-4">
      <!-- Mobile: Hamburger Menu (visible < 960px) -->
      <v-app-bar-nav-icon
        class="d-md-none mr-2"
        aria-label="Open navigation menu"
        @click="$emit('toggle-drawer')"
      />

      <!-- Logo (all screen sizes) -->
      <v-toolbar-title class="mr-4">
        <v-img
          src="/HNF1B-db_logo.svg"
          alt="HNF1B Database Logo"
          class="app-logo"
          contain
          max-height="48"
          width="184"
          min-width="140"
          @click="navigateHome"
        />
      </v-toolbar-title>

      <v-spacer />

      <!-- Desktop: Navigation Links (visible >= 960px) -->
      <div class="d-none d-md-flex align-center">
        <v-btn
          v-for="item in navigationItems"
          :key="item.route"
          :to="item.route"
          :prepend-icon="item.icon"
          variant="text"
          :class="{ 'v-btn--active': isActiveRoute(item.route) }"
          :aria-label="`Navigate to ${item.label}`"
        >
          {{ item.label }}
        </v-btn>

        <!-- Curate Menu (curator/admin only) -->
        <v-menu v-if="canCurate" location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              prepend-icon="mdi-pencil-plus"
              variant="text"
              aria-label="Curation menu"
            >
              Curate
              <v-icon right size="small">mdi-menu-down</v-icon>
            </v-btn>
          </template>
          <v-list role="menu" aria-label="Curation options">
            <v-list-item
              prepend-icon="mdi-account-plus"
              role="menuitem"
              aria-label="Create new phenopacket"
              @click="navigateToCreatePhenopacket"
            >
              <v-list-item-title>Create Phenopacket</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>

      <v-spacer />

      <!-- User Menu (all screen sizes) -->
      <div v-if="authStore.isAuthenticated" class="ml-4">
        <v-menu location="bottom">
          <template #activator="{ props }">
            <v-btn icon v-bind="props" aria-label="User menu">
              <v-avatar v-if="authStore.user" color="primary" size="small">
                <span class="text-white">{{ getUserInitials }}</span>
              </v-avatar>
              <v-icon v-else>mdi-account</v-icon>
            </v-btn>
          </template>
          <v-list role="menu" aria-label="User account options">
            <v-list-item v-if="authStore.user" role="presentation">
              <v-list-item-title>{{ authStore.user.username }}</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip :color="getRoleColor" size="x-small" dark>
                  {{ authStore.user.role }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
            <v-divider />
            <v-list-item
              prepend-icon="mdi-account-circle"
              role="menuitem"
              aria-label="View user profile"
              @click="goToUser"
            >
              <v-list-item-title>User Profile</v-list-item-title>
            </v-list-item>
            <v-list-item
              prepend-icon="mdi-logout"
              role="menuitem"
              aria-label="Log out of account"
              @click="handleLogout"
            >
              <v-list-item-title>Logout</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
      <div v-else class="ml-4">
        <v-btn icon to="/login" aria-label="Login">
          <v-icon>mdi-login</v-icon>
        </v-btn>
      </div>
    </v-container>
  </v-app-bar>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';
import { navigationItems } from '@/config/navigationItems';

// Emit toggle-drawer event for mobile menu
defineEmits(['toggle-drawer']);

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

/**
 * Get user initials for avatar
 */
const getUserInitials = computed(() => {
  if (!authStore.user?.username) return '?';
  return authStore.user.username.substring(0, 2).toUpperCase();
});

/**
 * Get role badge color
 */
const getRoleColor = computed(() => {
  const colors = {
    admin: 'red',
    curator: 'orange',
    viewer: 'grey',
  };
  return colors[authStore.user?.role] || 'grey';
});

/**
 * Check if user can curate (curator or admin)
 */
const canCurate = computed(() => {
  const userRole = authStore.user?.role;
  return userRole === 'curator' || userRole === 'admin';
});

/**
 * Check if a route is currently active
 */
const isActiveRoute = (routePath) => {
  return route.path === routePath;
};

/**
 * Navigate to home page
 */
const navigateHome = () => {
  router.push('/');
};

/**
 * Navigate to user profile
 */
const goToUser = () => {
  router.push({ name: 'User' });
};

/**
 * Navigate to create phenopacket page
 */
const navigateToCreatePhenopacket = () => {
  router.push({ name: 'CreatePhenopacket' });
};

/**
 * Log out user and redirect to home
 */
const handleLogout = async () => {
  await authStore.logout();
  router.push('/');
};
</script>

<style scoped>
.app-logo {
  cursor: pointer;
  flex-shrink: 0; /* Prevent logo from shrinking on small screens */
}

/* Active route indicator */
.v-btn--active {
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
