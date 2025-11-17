// src/stores/authStore.js - Pinia store for authentication state
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '@/api';

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null);
  const accessToken = ref(localStorage.getItem('access_token'));
  const refreshToken = ref(localStorage.getItem('refresh_token'));
  const isLoading = ref(false);
  const error = ref(null);

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
      const response = await apiClient.post('/auth/login', credentials);
      const { access_token, refresh_token } = response.data;

      // Store tokens
      accessToken.value = access_token;
      refreshToken.value = refresh_token;
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

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

    // Only call backend logout if we have a valid token and not skipping
    if (!skipBackendCall && accessToken.value) {
      try {
        await apiClient.post('/auth/logout');
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
    refreshToken.value = null;
    error.value = null;

    // Clear localStorage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');

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
    if (!refreshToken.value) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await apiClient.post('/auth/refresh', {
        refresh_token: refreshToken.value,
      });

      const { access_token, refresh_token: new_refresh_token } = response.data;

      // Update tokens (token rotation)
      accessToken.value = access_token;
      refreshToken.value = new_refresh_token;
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', new_refresh_token);

      window.logService.debug('Access token refreshed');

      return access_token;
    } catch (err) {
      window.logService.error('Token refresh failed', {
        error: err.message,
      });

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

  // Initialize: Load user if token exists
  async function initialize() {
    if (accessToken.value) {
      try {
        await fetchCurrentUser();
      } catch (err) {
        // Token might be expired, will be handled by interceptor
        window.logService.warn('Failed to initialize user session', {
          error: err.message,
        });
      }
    }
  }

  return {
    // State
    user,
    accessToken,
    refreshToken,
    isLoading,
    error,

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
  };
});
