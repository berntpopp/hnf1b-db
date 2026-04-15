/**
 * Unit tests for the authentication store (authStore).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

import { clearTokens, getAccessToken, persistTokens } from '@/api/session';

vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { apiClient } from '@/api';
import { useAuthStore } from '@/stores/authStore';

globalThis.window = globalThis.window || {};
globalThis.window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};

describe('Auth Store', () => {
  const originalDev = import.meta.env.DEV;
  const originalFlag = import.meta.env.VITE_ENABLE_DEV_AUTH;

  beforeEach(() => {
    setActivePinia(createPinia());
    clearTokens();
    vi.clearAllMocks();
    apiClient.post.mockReset();
    apiClient.get.mockReset();
    import.meta.env.DEV = true;
    import.meta.env.VITE_ENABLE_DEV_AUTH = 'true';
  });

  afterEach(() => {
    clearTokens();
    vi.restoreAllMocks();
    import.meta.env.DEV = originalDev;
    import.meta.env.VITE_ENABLE_DEV_AUTH = originalFlag;
  });

  describe('Initial State', () => {
    it('initializes with null user and no access token', () => {
      const authStore = useAuthStore();

      expect(authStore.user).toBeNull();
      expect(authStore.accessToken).toBeNull();
      expect('refreshToken' in authStore).toBe(false);
      expect(authStore.isLoading).toBe(false);
      expect(authStore.error).toBeNull();
      expect(getAccessToken()).toBeNull();
    });

    it('initializes from the in-memory access token when one already exists', () => {
      persistTokens({ accessToken: 'mock_access_token' });

      const authStore = useAuthStore();

      expect(authStore.accessToken).toBe('mock_access_token');
    });
  });

  describe('Computed Properties', () => {
    it('computes isAuthenticated correctly', () => {
      const authStore = useAuthStore();

      expect(authStore.isAuthenticated).toBe(false);

      authStore.accessToken = 'test_token';
      expect(authStore.isAuthenticated).toBe(false);

      authStore.accessToken = null;
      authStore.user = { username: 'test' };
      expect(authStore.isAuthenticated).toBe(false);

      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test' };
      expect(authStore.isAuthenticated).toBe(true);
    });
  });

  describe('Login Action', () => {
    it('stores only the access token in memory and loads the current user', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'mock_access_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });

      apiClient.get.mockResolvedValueOnce({
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'viewer',
          permissions: ['phenopackets:read'],
        },
      });

      const success = await authStore.login({
        username: 'testuser',
        password: 'password123',
      });

      expect(success).toBe(true);
      expect(authStore.accessToken).toBe('mock_access_token');
      expect(getAccessToken()).toBe('mock_access_token');
      expect(authStore.user.username).toBe('testuser');
      expect(window.logService.info).toHaveBeenCalledWith('User logged in successfully', {
        username: 'testuser',
      });
    });

    it('surfaces login failures without mutating the session', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockRejectedValueOnce({
        response: { data: { detail: 'Invalid credentials' } },
      });

      await expect(
        authStore.login({ username: 'testuser', password: 'wrongpassword' })
      ).rejects.toThrow();

      expect(authStore.error).toBe('Invalid credentials');
      expect(getAccessToken()).toBeNull();
    });
  });

  describe('Logout Action', () => {
    it('calls backend logout once and clears the session state', async () => {
      const authStore = useAuthStore();

      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test', id: 1 };
      persistTokens({ accessToken: 'test_token' });

      apiClient.post.mockResolvedValueOnce({
        data: { message: 'Logged out successfully' },
      });

      await authStore.logout();

      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout', null, {
        withCredentials: true,
      });
      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
    });

    it('still attempts backend logout when no access token is present', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({ data: { message: 'ok' } });

      await authStore.logout();

      expect(apiClient.post).toHaveBeenCalledWith('/auth/logout', null, {
        withCredentials: true,
      });
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
    });

    it('still clears the session if the backend logout call fails', async () => {
      const authStore = useAuthStore();

      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test' };
      persistTokens({ accessToken: 'test_token' });

      apiClient.post.mockRejectedValueOnce(new Error('API Error'));

      await authStore.logout();

      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
      expect(window.logService.warn).toHaveBeenCalled();
    });
  });

  describe('Fetch Current User Action', () => {
    it('fetches the current user successfully', async () => {
      const authStore = useAuthStore();
      authStore.accessToken = 'test_token';

      apiClient.get.mockResolvedValueOnce({
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'admin',
          permissions: ['users:read', 'users:write'],
        },
      });

      await authStore.fetchCurrentUser();

      expect(authStore.user.username).toBe('testuser');
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });
  });

  describe('Refresh Access Token Action', () => {
    it('uses the cookie-backed refresh endpoint and rotates only the access token', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'new_access_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });

      const result = await authStore.refreshAccessToken();

      expect(result).toBe('new_access_token');
      expect(apiClient.post).toHaveBeenCalledWith('/auth/refresh', null, {
        withCredentials: true,
      });
      expect(authStore.accessToken).toBe('new_access_token');
      expect(getAccessToken()).toBe('new_access_token');
    });

    it('clears the in-memory session when refresh fails', async () => {
      const authStore = useAuthStore();
      authStore.accessToken = 'old_token';
      authStore.user = { username: 'test' };
      persistTokens({ accessToken: 'old_token' });

      apiClient.post.mockRejectedValueOnce(new Error('Invalid refresh token'));

      await expect(authStore.refreshAccessToken()).rejects.toThrow('Invalid refresh token');

      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
    });
  });

  describe('Initialize Action', () => {
    it('fetches the current user when an access token already exists in memory', async () => {
      persistTokens({ accessToken: 'existing_token' });

      apiClient.get.mockResolvedValueOnce({
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'viewer',
        },
      });

      const authStore = useAuthStore();
      await authStore.initialize();

      expect(apiClient.post).not.toHaveBeenCalled();
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
      expect(authStore.user.username).toBe('testuser');
    });

    it('attempts one refresh bootstrap before loading the current user', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'bootstrapped_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });
      apiClient.get.mockResolvedValueOnce({
        data: { id: 1, username: 'testuser', role: 'viewer' },
      });

      await authStore.initialize();

      expect(apiClient.post).toHaveBeenCalledWith('/auth/refresh', null, {
        withCredentials: true,
      });
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
      expect(authStore.accessToken).toBe('bootstrapped_token');
      expect(authStore.user.username).toBe('testuser');
    });

    it('stays anonymous when refresh bootstrap fails', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockRejectedValueOnce(new Error('Refresh failed'));

      await authStore.initialize();

      expect(apiClient.get).not.toHaveBeenCalled();
      expect(authStore.user).toBeNull();
      expect(authStore.accessToken).toBeNull();
      expect(window.logService.warn).toHaveBeenCalledWith(
        'Failed to initialize user session',
        expect.any(Object)
      );
    });
  });

  describe('Dev Quick Login', () => {
    it('stores only the access token from dev quick-login', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'dev_access_token',
          refresh_token: 'ignored-refresh-token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });
      apiClient.get.mockResolvedValueOnce({
        data: { id: 1, username: 'dev-admin', role: 'admin' },
      });

      await authStore.devLoginAs('dev-admin');

      expect(authStore.accessToken).toBe('dev_access_token');
      expect(getAccessToken()).toBe('dev_access_token');
      expect('refreshToken' in authStore).toBe(false);
    });
  });
});
