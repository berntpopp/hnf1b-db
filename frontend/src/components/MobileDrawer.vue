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
    <v-list density="compact" nav>
      <v-list-item
        v-for="item in navigationItems"
        :key="item.route"
        :to="item.route"
        :prepend-icon="item.icon"
        :title="item.label"
        :active="isActiveRoute(item.route)"
        @click="closeDrawer"
      />
    </v-list>

    <v-divider />

    <!-- User Menu (authenticated) -->
    <v-list v-if="isAuthenticated" density="compact">
      <v-list-subheader>Account</v-list-subheader>
      <v-list-item
        prepend-icon="mdi-account-circle"
        title="User Profile"
        to="/user"
        @click="closeDrawer"
      />
      <v-list-item prepend-icon="mdi-logout" title="Logout" @click="handleLogout" />
    </v-list>

    <!-- Login (not authenticated) -->
    <v-list v-else density="compact">
      <v-list-item prepend-icon="mdi-login" title="Login" to="/login" @click="closeDrawer" />
    </v-list>
  </v-navigation-drawer>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { navigationItems } from '@/config/navigationItems';
import { authStatus, removeToken } from '@/utils/auth';

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true,
  },
});

const emit = defineEmits(['update:modelValue']);

const router = useRouter();
const route = useRoute();

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
const isAuthenticated = computed(() => authStatus.value);

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
const handleLogout = () => {
  closeDrawer();
  removeToken();
  router.push('/');
};
</script>

<style scoped>
.v-img {
  cursor: pointer;
}
</style>
