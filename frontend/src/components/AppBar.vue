<template>
  <v-app-bar app color="teal" dark elevation="2">
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
          max-width="184"
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
      </div>

      <v-spacer />

      <!-- User Menu (all screen sizes) -->
      <div v-if="isAuthenticated" class="ml-4">
        <v-menu location="bottom">
          <template #activator="{ props }">
            <v-btn icon v-bind="props" aria-label="User menu">
              <v-icon>mdi-account</v-icon>
            </v-btn>
          </template>
          <v-list>
            <v-list-item prepend-icon="mdi-account-circle" @click="goToUser">
              <v-list-item-title>User Profile</v-list-item-title>
            </v-list-item>
            <v-list-item prepend-icon="mdi-logout" @click="handleLogout">
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
import { authStatus, removeToken } from '@/utils/auth';
import { navigationItems } from '@/config/navigationItems';

// Emit toggle-drawer event for mobile menu
defineEmits(['toggle-drawer']);

const router = useRouter();
const route = useRoute();

/**
 * Reactive authentication status from globally reactive variable.
 * Updates automatically when token is set or removed.
 */
const isAuthenticated = computed(() => authStatus.value);

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
 * Log out user by removing token and redirecting to home
 */
const handleLogout = () => {
  removeToken();
  router.push('/');
};
</script>

<style scoped>
.app-logo {
  cursor: pointer;
}

/* Active route indicator */
.v-btn--active {
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
