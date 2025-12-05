<template>
  <v-navigation-drawer v-model="isOpen" location="left" temporary width="280">
    <!-- Header with Logo -->
    <v-list-item class="px-4 py-3">
      <v-img
        src="/HNF1B-db_logo.svg"
        alt="HNF1B Database Logo"
        max-height="40"
        max-width="150"
        contain
        @click="navigateHome"
      />
    </v-list-item>

    <v-divider />

    <!-- Navigation Items -->
    <v-list density="compact" nav role="navigation" aria-label="Main navigation">
      <v-list-item
        v-for="item in navigationItems"
        :key="item.route"
        :to="item.route"
        :prepend-icon="item.icon"
        :title="item.label"
        :active="isActiveRoute(item.route)"
        :aria-label="`Navigate to ${item.label}`"
        role="link"
        @click="closeDrawer"
      />
    </v-list>

    <v-divider />

    <!-- Curate Menu (curator/admin only) -->
    <v-list v-if="canCurate" density="compact" role="navigation" aria-label="Curation actions">
      <v-list-subheader>Curate</v-list-subheader>
      <v-list-item
        prepend-icon="mdi-account-plus"
        title="Create Phenopacket"
        to="/phenopackets/create"
        aria-label="Create new phenopacket"
        role="link"
        @click="closeDrawer"
      />
    </v-list>

    <v-divider v-if="canCurate" />

    <!-- User Menu (authenticated) -->
    <v-list v-if="isAuthenticated" density="compact" role="menu" aria-label="Account menu">
      <v-list-subheader>Account</v-list-subheader>
      <v-list-item
        prepend-icon="mdi-account-circle"
        title="User Profile"
        to="/user"
        aria-label="View user profile"
        role="menuitem"
        @click="closeDrawer"
      />
      <v-list-item
        prepend-icon="mdi-logout"
        title="Logout"
        aria-label="Log out of account"
        role="menuitem"
        @click="handleLogout"
      />
    </v-list>

    <!-- Login (not authenticated) -->
    <v-list v-else density="compact" role="navigation" aria-label="Authentication">
      <v-list-item
        prepend-icon="mdi-login"
        title="Login"
        to="/login"
        aria-label="Log in to account"
        role="link"
        @click="closeDrawer"
      />
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { navigationItems } from '@/config/navigationItems';
import { useAuthStore } from '@/stores/authStore';

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
});

const emit = defineEmits(['update:modelValue']);

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

/**
 * Two-way binding for drawer open/close state
 */
const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

/**
 * Reactive authentication status
 */
const isAuthenticated = computed(() => authStore.isAuthenticated);

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
 * Close the drawer
 */
const closeDrawer = () => {
  isOpen.value = false;
};

/**
 * Navigate to home and close drawer
 */
const navigateHome = () => {
  router.push('/');
  closeDrawer();
};

/**
 * Log out user, close drawer, and redirect to home
 */
const handleLogout = async () => {
  closeDrawer();
  await authStore.logout();
  router.push('/');
};
</script>

<style scoped>
.v-img {
  cursor: pointer;
}
</style>
