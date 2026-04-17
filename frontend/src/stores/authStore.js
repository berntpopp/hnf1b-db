// src/stores/authStore.js - Pinia store for authentication state
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiClient } from '@/api';
import {
  getDevQuickLoginBackendUnavailableMessage,
  getDevQuickLoginDisabledMessage,
  isDevQuickLoginEnabled,
} from '@/config/devAuth';
import { clearTokens, getAccessToken, persistTokens } from '@/api/session';

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null);
  const accessToken = ref(getAccessToken());
  const isLoading = ref(false);
  const error = ref(null);
  const hasInitialized = ref(false);
  let initializationPromise = null;

  // Getters
  const isAuthenticated = computed(() => !!accessToken.value && !!user.value);
  const isAdmin = computed(() => user.value?.role === 'admin');
  const isCurator = computed(() => ['admin', 'curator'].includes(user.value?.role));
  const userPermissions = computed(() => user.value?.permissions || []);

  // Actions
  async function login(credentials) {
    isLoading.value = true;
    error.value = null;

    try {
      const response = await apiClient.post('/auth/login', credentials, {
        withCredentials: true,
      });
      const { access_token } = response.data;

      // Access token stays in memory only; refresh lives in the HttpOnly cookie.
      accessToken.value = access_token;
      persistTokens({ accessToken: access_token });

      // Fetch user info
      await fetchCurrentUser();

      window.logService.info('User logged in successfully', {
        username: user.value?.username,
      });

      return true;
    } catch (err) {
      error.value = err.response?.data?.detail || 'Login failed';
      window.logService.error('Login failed', {
        error: error.value,
      });
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function logout(skipBackendCall = false) {
    isLoading.value = true;

    if (!skipBackendCall) {
      try {
        await apiClient.post('/auth/logout', null, { withCredentials: true });
      } catch (err) {
        // Continue with logout even if backend call fails
        window.logService.warn('Logout API call failed, continuing with local logout', {
          error: err.message,
        });
      }
    }

    // Clear state
    user.value = null;
    accessToken.value = null;
    error.value = null;

    // Clear in-memory token storage
    clearTokens();

    isLoading.value = false;

    window.logService.info('User logged out');
  }

  async function fetchCurrentUser() {
    if (!accessToken.value) {
      return;
    }

    isLoading.value = true;

    try {
      const response = await apiClient.get('/auth/me');
      user.value = response.data;

      window.logService.debug('User info fetched', {
        username: user.value?.username,
        role: user.value?.role,
      });
    } catch (err) {
      window.logService.error('Failed to fetch user info', {
        error: err.message,
      });

      // If token is invalid, clear auth state (skip backend logout call since token is already invalid)
      if (err.response?.status === 401) {
        await logout(true);
      }

      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  async function refreshAccessToken() {
    const wasAuthenticated = !!user.value;
    try {
      const response = await apiClient.post('/auth/refresh', null, {
        withCredentials: true,
      });

      const { access_token } = response.data;

      // Update the short-lived access token in memory only.
      accessToken.value = access_token;
      persistTokens({ accessToken: access_token });

      window.logService.debug('Access token refreshed');

      return access_token;
    } catch (err) {
      if (wasAuthenticated) {
        window.logService.error('Token refresh failed', {
          error: err.message,
        });
      } else {
        window.logService.debug('Anonymous session refresh rejected (expected)', {
          error: err.message,
        });
      }

      // If refresh fails, logout user (skip backend call since token is already invalid)
      await logout(true);
      throw err;
    }
  }

  async function changePassword(currentPassword, newPassword) {
    isLoading.value = true;
    error.value = null;

    try {
      await apiClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });

      window.logService.info('Password changed successfully');

      return true;
    } catch (err) {
      error.value = err.response?.data?.detail || 'Password change failed';
      window.logService.error('Password change failed', {
        error: error.value,
      });
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  // Wave 5a Layer 4 — the DEV gate is critical. Vite replaces
  // import.meta.env.DEV with literal `false` during production build
  // and Rollup DCE eliminates the entire function body, including
  // the URL string literal `/dev/login-as/` (which apiClient resolves
  // to /api/v2/dev/login-as/ at request time). Never read
  // import.meta.env.DEV into a variable first — keep the literal
  // inside the guard so the static replacement is structural.
  async function devLoginAs(username) {
    if (!import.meta.env.DEV) return;

    if (!isDevQuickLoginEnabled()) {
      const message = getDevQuickLoginDisabledMessage();
      error.value = message;
      throw new Error(message);
    }

    isLoading.value = true;
    error.value = null;
    try {
      const { data } = await apiClient.post(`/dev/login-as/${username}`);
      accessToken.value = data.access_token;
      persistTokens({ accessToken: data.access_token });
      await fetchCurrentUser();
      window.logService.info('dev quick-login', { username });
      return true;
    } catch (err) {
      if (err.response?.status === 404) {
        error.value = getDevQuickLoginBackendUnavailableMessage();
      } else {
        error.value = err.response?.data?.detail || 'Dev quick-login failed';
      }
      window.logService.error('dev quick-login failed', { username, error: err.message });
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  // Initialize: Load user if token exists
  async function initialize() {
    if (initializationPromise) {
      return initializationPromise;
    }

    initializationPromise = (async () => {
      if (accessToken.value) {
        try {
          await fetchCurrentUser();
        } catch (err) {
          // Token might be expired, will be handled by interceptor
          const level = user.value ? 'warn' : 'debug';
          window.logService[level]('Failed to initialize user session', {
            error: err.message,
          });
        }
        return;
      }

      try {
        await refreshAccessToken();
        await fetchCurrentUser();
      } catch (err) {
        // Anonymous visitor — refresh rejection is expected.
        window.logService.debug('Anonymous session bootstrap skipped', {
          error: err.message,
        });
      }
    })();

    try {
      await initializationPromise;
    } finally {
      hasInitialized.value = true;
      initializationPromise = null;
    }
  }

  return {
    // State
    user,
    accessToken,
    isLoading,
    error,
    hasInitialized,

    // Getters
    isAuthenticated,
    isAdmin,
    isCurator,
    userPermissions,

    // Actions
    login,
    logout,
    fetchCurrentUser,
    refreshAccessToken,
    changePassword,
    initialize,
    devLoginAs,
  };
});
