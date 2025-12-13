<template>
  <v-app-bar app color="teal" dark elevation="2" style="z-index: 1009">
    <v-container fluid class="d-flex align-center px-2 px-sm-4">
      <!-- Mobile: Hamburger Menu (visible < 960px) -->
      <v-app-bar-nav-icon
        class="d-md-none mr-1 mr-sm-2"
        aria-label="Open navigation menu"
        @click="$emit('toggle-drawer')"
      />

      <!-- Logo (all screen sizes) - wrapped in tooltip -->
      <v-tooltip location="bottom" :text="tooltipText" :aria-label="tooltipText">
        <template #activator="{ props: tooltipProps }">
          <div
            class="logo-container mr-2 mr-sm-4"
            v-bind="tooltipProps"
            role="button"
            tabindex="0"
            aria-label="HNF1B Database - Click to go home"
            @click="navigateHome"
            @keydown.enter="navigateHome"
          >
            <img
              src="/HNF1B-db_logo.svg"
              alt="HNF1B Database Logo"
              class="app-logo"
              :style="{
                width: logoWidth + 'px',
                height: 'auto',
                maxHeight: logoMaxHeight + 'px',
              }"
            />
          </div>
        </template>
      </v-tooltip>

      <v-spacer />

      <!-- Desktop: Navigation Links (visible >= 960px) - absolutely centered -->
      <div class="d-none d-md-flex align-center nav-group-centered">
        <v-tooltip
          v-for="item in navigationItems"
          :key="item.route"
          location="bottom"
          :text="item.tooltip"
          :aria-label="item.tooltip"
        >
          <template #activator="{ props: navTooltipProps }">
            <v-btn
              v-bind="navTooltipProps"
              :to="item.route"
              :prepend-icon="item.icon"
              variant="text"
              :class="{ 'v-btn--active': isActiveRoute(item.route) }"
              :aria-label="`${item.label} - ${item.tooltip}`"
            >
              {{ item.label }}
            </v-btn>
          </template>
        </v-tooltip>

        <!-- Curate Menu (curator/admin only) -->
        <v-menu v-if="canCurate" location="bottom">
          <template #activator="{ props: menuProps }">
            <v-tooltip
              location="bottom"
              text="Data curation actions"
              aria-label="Data curation actions"
            >
              <template #activator="{ props: curateTooltipProps }">
                <v-btn
                  v-bind="{ ...menuProps, ...curateTooltipProps }"
                  prepend-icon="mdi-pencil-plus"
                  variant="text"
                  aria-label="Curate - Data curation actions"
                >
                  Curate
                  <v-icon right size="small">mdi-menu-down</v-icon>
                </v-btn>
              </template>
            </v-tooltip>
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
              v-if="isAdmin"
              prepend-icon="mdi-shield-crown"
              role="menuitem"
              aria-label="Admin Dashboard"
              @click="goToAdmin"
            >
              <v-list-item-title>Admin Dashboard</v-list-item-title>
            </v-list-item>
            <v-divider v-if="isAdmin" />
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
        <v-tooltip
          location="bottom"
          text="Sign in to your account"
          aria-label="Sign in to your account"
        >
          <template #activator="{ props: loginTooltipProps }">
            <v-btn icon to="/login" aria-label="Login" v-bind="loginTooltipProps">
              <v-icon>mdi-login</v-icon>
            </v-btn>
          </template>
        </v-tooltip>
      </div>
    </v-container>
  </v-app-bar>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useDisplay } from 'vuetify';
import { useAuthStore } from '@/stores/authStore';
import { navigationItems } from '@/config/navigationItems';

// Emit toggle-drawer event for mobile menu
defineEmits(['toggle-drawer']);

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const { xs, smAndDown } = useDisplay();

/**
 * Tooltip text describing the project essence
 */
const tooltipText = 'HNF1B Database: Curated clinical & genetic variants';

/**
 * Responsive logo width based on screen size
 */
const logoWidth = computed(() => {
  if (xs.value) return 120; // Extra small screens
  if (smAndDown.value) return 150; // Small screens
  return 184; // Default (medium and up)
});

/**
 * Responsive logo max height based on screen size
 */
const logoMaxHeight = computed(() => {
  if (xs.value) return 36; // Extra small screens
  if (smAndDown.value) return 42; // Small screens
  return 48; // Default (medium and up)
});

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
 * Check if user is admin
 */
const isAdmin = computed(() => {
  return authStore.user?.role === 'admin';
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
 * Navigate to admin dashboard
 */
const goToAdmin = () => {
  router.push({ name: 'AdminDashboard' });
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
/* Logo container - prevents flex shrinking and ensures visibility */
.logo-container {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  overflow: visible;
}

.app-logo {
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.3s ease-in-out;
}

/* Subtle pulse animation on hover */
.logo-container:hover .app-logo {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}

/* Navigation group - absolutely centered in appbar */
.nav-group-centered {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  gap: 4px;
}

/* Active route indicator */
.v-btn--active {
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
