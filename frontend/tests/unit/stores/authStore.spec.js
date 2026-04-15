/**
 * Unit tests for the authentication store (authStore)
 *
 * Covers the public auth flows against the release-safe in-memory
 * session helpers rather than persistent browser storage.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';

import { clearTokens, getAccessToken, getRefreshToken, persistTokens } from '@/api/session';

// Mock the API module with named export - must be before imports that use it
vi.mock('@/api', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Import after mock is set up
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api';

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
    it('initializes with null user and no tokens', () => {
      const authStore = useAuthStore();

      expect(authStore.user).toBeNull();
      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.isLoading).toBe(false);
      expect(authStore.error).toBeNull();
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
    });

    it('initializes from the in-memory session when tokens already exist', () => {
      persistTokens({ accessToken: 'mock_access_token', refreshToken: 'mock_refresh_token' });

      const authStore = useAuthStore();

      expect(authStore.accessToken).toBe('mock_access_token');
      expect(authStore.refreshToken).toBe('mock_refresh_token');
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

    it('computes role helpers correctly', () => {
      const authStore = useAuthStore();

      expect(authStore.isAdmin).toBe(false);
      expect(authStore.isCurator).toBe(false);

      authStore.user = { role: 'curator' };
      expect(authStore.isAdmin).toBe(false);
      expect(authStore.isCurator).toBe(true);

      authStore.user = { role: 'admin' };
      expect(authStore.isAdmin).toBe(true);
      expect(authStore.isCurator).toBe(true);
    });

    it('returns permissions from the current user', () => {
      const authStore = useAuthStore();

      expect(authStore.userPermissions).toEqual([]);

      authStore.user = { permissions: ['read:data', 'write:data'] };
      expect(authStore.userPermissions).toEqual(['read:data', 'write:data']);
    });
  });

  describe('Login Action', () => {
    it('stores issued tokens in memory and loads the current user', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'mock_access_token',
          refresh_token: 'mock_refresh_token',
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
      expect(authStore.refreshToken).toBe('mock_refresh_token');
      expect(authStore.user.username).toBe('testuser');
      expect(getAccessToken()).toBe('mock_access_token');
      expect(getRefreshToken()).toBe('mock_refresh_token');
      expect(window.logService.info).toHaveBeenCalledWith('User logged in successfully', {
        username: 'testuser',
      });
    });

    it('clears the error state before a new login attempt', async () => {
      const authStore = useAuthStore();
      authStore.error = 'Previous error';

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'token',
          refresh_token: 'refresh',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });
      apiClient.get.mockResolvedValueOnce({
        data: { id: 1, username: 'test' },
      });

      await authStore.login({ username: 'test', password: 'pass' });

      expect(authStore.error).toBeNull();
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
      expect(getRefreshToken()).toBeNull();
    });
  });

  describe('Logout Action', () => {
    it('clears the session tokens and local store state', async () => {
      const authStore = useAuthStore();

      authStore.accessToken = 'test_token';
      authStore.refreshToken = 'test_refresh';
      authStore.user = { username: 'test', id: 1 };
      persistTokens({ accessToken: 'test_token', refreshToken: 'test_refresh' });

      apiClient.post.mockResolvedValueOnce({
        data: { message: 'Logged out successfully' },
      });

      await authStore.logout();

      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
      expect(window.logService.info).toHaveBeenCalledWith('User logged out');
    });

    it('still clears the session if the backend logout call fails', async () => {
      const authStore = useAuthStore();

      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test' };
      persistTokens({ accessToken: 'test_token', refreshToken: 'test_refresh' });

      apiClient.post.mockRejectedValueOnce(new Error('API Error'));

      await authStore.logout();

      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
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
      expect(window.logService.debug).toHaveBeenCalled();
    });

    it('logs out when fetching the current user returns 401', async () => {
      const authStore = useAuthStore();
      authStore.accessToken = 'test_token';
      persistTokens({ accessToken: 'test_token', refreshToken: 'test_refresh' });

      apiClient.get.mockRejectedValueOnce({
        response: { status: 401 },
        message: 'Unauthorized',
      });
      apiClient.post.mockResolvedValueOnce({ data: {} });

      await expect(authStore.fetchCurrentUser()).rejects.toThrow();

      expect(authStore.accessToken).toBeNull();
      expect(getAccessToken()).toBeNull();
    });
  });

  describe('Refresh Access Token Action', () => {
    it('rotates tokens in memory', async () => {
      const authStore = useAuthStore();
      authStore.refreshToken = 'old_refresh_token';

      apiClient.post.mockResolvedValueOnce({
        data: {
          access_token: 'new_access_token',
          refresh_token: 'new_refresh_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      });

      const result = await authStore.refreshAccessToken();

      expect(result).toBe('new_access_token');
      expect(authStore.accessToken).toBe('new_access_token');
      expect(authStore.refreshToken).toBe('new_refresh_token');
      expect(getAccessToken()).toBe('new_access_token');
      expect(getRefreshToken()).toBe('new_refresh_token');
      expect(window.logService.debug).toHaveBeenCalledWith('Access token refreshed');
    });

    it('clears the in-memory session when refresh fails', async () => {
      const authStore = useAuthStore();
      authStore.refreshToken = 'invalid_refresh_token';
      authStore.accessToken = 'old_token';
      authStore.user = { username: 'test' };
      persistTokens({ accessToken: 'old_token', refreshToken: 'invalid_refresh_token' });

      apiClient.post.mockRejectedValueOnce(new Error('Invalid refresh token'));

      await expect(authStore.refreshAccessToken()).rejects.toThrow('Invalid refresh token');

      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
      expect(window.logService.error).toHaveBeenCalled();
    });
  });

  describe('Change Password Action', () => {
    it('calls the backend password change endpoint', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: { message: 'Password changed successfully' },
      });

      const success = await authStore.changePassword('oldpass', 'newpass');

      expect(success).toBe(true);
      expect(authStore.error).toBeNull();
      expect(apiClient.post).toHaveBeenCalledWith('/auth/change-password', {
        current_password: 'oldpass',
        new_password: 'newpass',
      });
      expect(window.logService.info).toHaveBeenCalledWith('Password changed successfully');
    });

    it('surfaces password change failures', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Current password is incorrect',
          },
        },
      });

      await expect(authStore.changePassword('wrongpass', 'newpass')).rejects.toThrow();

      expect(authStore.error).toBe('Current password is incorrect');
      expect(window.logService.error).toHaveBeenCalled();
    });
  });

  describe('Initialize Action', () => {
    it('fetches the current user when an in-memory token exists', async () => {
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

      expect(authStore.user.username).toBe('testuser');
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });

    it('does not fetch the current user if no token exists', async () => {
      const authStore = useAuthStore();
      await authStore.initialize();

      expect(apiClient.get).not.toHaveBeenCalled();
      expect(authStore.user).toBeNull();
    });

    it('logs a warning if initialization cannot restore the current user', async () => {
      persistTokens({ accessToken: 'invalid_token' });

      apiClient.get.mockRejectedValueOnce({
        response: { status: 401 },
        message: 'Unauthorized',
      });
      apiClient.post.mockResolvedValueOnce({ data: {} });

      const authStore = useAuthStore();
      await authStore.initialize();

      expect(window.logService.warn).toHaveBeenCalledWith(
        'Failed to initialize user session',
        expect.any(Object)
      );
    });
  });

  describe('Dev Quick Login', () => {
    it('refuses quick-login when the frontend flag is disabled', async () => {
      import.meta.env.VITE_ENABLE_DEV_AUTH = 'false';
      const authStore = useAuthStore();

      await expect(authStore.devLoginAs('dev-curator')).rejects.toThrow(
        'Dev quick-login is disabled'
      );

      expect(authStore.error).toContain('VITE_ENABLE_DEV_AUTH=true');
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('surfaces backend dev-auth misconfiguration on 404', async () => {
      const authStore = useAuthStore();
      apiClient.post.mockRejectedValueOnce({
        response: { status: 404, data: { detail: 'Not Found' } },
        message: 'Request failed with status code 404',
      });

      await expect(authStore.devLoginAs('dev-curator')).rejects.toThrow();

      expect(authStore.error).toContain('ENABLE_DEV_AUTH=true');
    });
  });
});
