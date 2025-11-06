<template>
  <v-app-bar app color="teal" dark>
    <v-container fluid>
      <v-row align="center" justify="space-between" no-gutters>
        <!-- Left Section: Logo -->
        <v-col>
          <v-img
            src="/HNF1B-db_logo.webp"
            class="app-logo ml-auto"
            contain
            max-height="48"
            max-width="184"
            @click="navigateHome"
          />
        </v-col>

        <!-- Middle Section: Navigation Links with Dividers -->
        <v-col class="d-flex align-center px-10">
          <v-divider class="border-opacity-100" vertical />
          <v-toolbar-items>
            <v-btn text to="/phenopackets"> Phenopackets </v-btn>
            <v-btn text to="/publications"> Publications </v-btn>
            <v-btn text to="/variants"> Variants </v-btn>
            <v-btn text to="/aggregations"> Aggregations </v-btn>
          </v-toolbar-items>
          <v-divider class="border-opacity-100" vertical />
        </v-col>

        <!-- Right Section: Login Controls -->
        <v-col>
          <div v-if="isAuthenticated">
            <v-menu v-model="menu" offset-y>
              <template #activator="{ props }">
                <v-btn icon v-bind="props">
                  <v-icon>mdi-account</v-icon>
                </v-btn>
              </template>
              <v-list>
                <v-list-item @click="goToUser">
                  <v-list-item-title>User Profile</v-list-item-title>
                </v-list-item>
                <v-list-item @click="handleLogout">
                  <v-list-item-title>Logout</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </div>
          <div v-else>
            <v-btn icon to="/login">
              <v-icon>mdi-login</v-icon>
            </v-btn>
          </div>
        </v-col>
      </v-row>
    </v-container>
  </v-app-bar>
</template>

<script>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { authStatus, removeToken } from '@/utils/auth';

export default {
  name: 'AppBar',
  setup() {
    const router = useRouter();
    const menu = ref(false);

    /**
     * Reactive authentication status from a globally reactive variable.
     * This updates automatically when the token is set or removed.
     */
    const isAuthenticated = computed(() => authStatus.value);

    /**
     * Navigates to the home page.
     */
    const navigateHome = () => {
      router.push('/');
    };

    /**
     * Navigates to the user profile and closes the menu.
     */
    const goToUser = () => {
      menu.value = false;
      router.push({ name: 'User' });
    };

    /**
     * Logs out the user by removing the token,
     * closing the menu, and redirecting to the home page.
     */
    const handleLogout = () => {
      menu.value = false;
      removeToken();
      router.push('/');
    };

    return {
      navigateHome,
      isAuthenticated,
      menu,
      goToUser,
      handleLogout,
    };
  },
};
</script>

<style scoped>
.app-logo {
  cursor: pointer;
}
</style>
