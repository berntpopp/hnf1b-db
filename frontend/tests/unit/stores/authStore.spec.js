/**
 * Unit tests for the authentication store (authStore)
 *
 * Tests cover:
 * - State initialization
 * - Computed properties (isAuthenticated, isAdmin, isCurator, userPermissions)
 * - Login flow with token storage
 * - Logout with cleanup
 * - Token refresh
 * - User fetching
 * - Password change
 * - Store initialization from localStorage
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useAuthStore } from '@/stores/authStore';
import apiClient from '@/api/index';

// Mock the API client
vi.mock('@/api/index', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn((key) => store[key] || null),
    setItem: vi.fn((key, value) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock window.logService
window.logService = {
  info: vi.fn(),
  error: vi.fn(),
  warn: vi.fn(),
  debug: vi.fn(),
};

describe('Auth Store', () => {
  beforeEach(() => {
    // Create a fresh Pinia instance for each test
    setActivePinia(createPinia());

    // Clear mocks
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should initialize with null user and tokens', () => {
      const authStore = useAuthStore();

      expect(authStore.user).toBeNull();
      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.isLoading).toBe(false);
      expect(authStore.error).toBeNull();
    });

    it('should initialize with token from localStorage if present', () => {
      localStorageMock.setItem('access_token', 'mock_access_token');
      localStorageMock.setItem('refresh_token', 'mock_refresh_token');

      const authStore = useAuthStore();

      expect(authStore.accessToken).toBe('mock_access_token');
      expect(authStore.refreshToken).toBe('mock_refresh_token');
    });
  });

  describe('Computed Properties', () => {
    it('should compute isAuthenticated correctly', () => {
      const authStore = useAuthStore();

      // Not authenticated initially
      expect(authStore.isAuthenticated).toBe(false);

      // Set token but no user - still not authenticated
      authStore.accessToken = 'test_token';
      expect(authStore.isAuthenticated).toBe(false);

      // Set user but no token - still not authenticated
      authStore.accessToken = null;
      authStore.user = { username: 'test' };
      expect(authStore.isAuthenticated).toBe(false);

      // Both token and user - authenticated
      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test' };
      expect(authStore.isAuthenticated).toBe(true);
    });

    it('should compute isAdmin correctly', () => {
      const authStore = useAuthStore();

      expect(authStore.isAdmin).toBe(false);

      authStore.user = { role: 'viewer' };
      expect(authStore.isAdmin).toBe(false);

      authStore.user = { role: 'curator' };
      expect(authStore.isAdmin).toBe(false);

      authStore.user = { role: 'admin' };
      expect(authStore.isAdmin).toBe(true);
    });

    it('should compute isCurator correctly', () => {
      const authStore = useAuthStore();

      expect(authStore.isCurator).toBe(false);

      authStore.user = { role: 'viewer' };
      expect(authStore.isCurator).toBe(false);

      authStore.user = { role: 'curator' };
      expect(authStore.isCurator).toBe(true);

      authStore.user = { role: 'admin' };
      expect(authStore.isCurator).toBe(false);
    });

    it('should compute userPermissions correctly', () => {
      const authStore = useAuthStore();

      expect(authStore.userPermissions).toEqual([]);

      authStore.user = {
        permissions: ['read:data', 'write:data', 'delete:data'],
      };

      expect(authStore.userPermissions).toEqual(['read:data', 'write:data', 'delete:data']);
    });
  });

  describe('Login Action', () => {
    it('should login successfully and store tokens', async () => {
      const authStore = useAuthStore();

      const mockResponse = {
        data: {
          access_token: 'mock_access_token',
          refresh_token: 'mock_refresh_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      };

      const mockUserResponse = {
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'viewer',
          permissions: ['phenopackets:read'],
        },
      };

      apiClient.post.mockResolvedValueOnce(mockResponse);
      apiClient.get.mockResolvedValueOnce(mockUserResponse);

      const success = await authStore.login({
        username: 'testuser',
        password: 'password123',
      });

      expect(success).toBe(true);
      expect(authStore.accessToken).toBe('mock_access_token');
      expect(authStore.refreshToken).toBe('mock_refresh_token');
      expect(authStore.user).toEqual(mockUserResponse.data);
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'mock_access_token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'mock_refresh_token');
      expect(window.logService.info).toHaveBeenCalledWith('User logged in successfully', {
        user: 'testuser',
      });
    });

    it('should handle login failure', async () => {
      const authStore = useAuthStore();

      const mockError = {
        response: {
          data: {
            detail: 'Invalid credentials',
          },
        },
      };

      apiClient.post.mockRejectedValueOnce(mockError);

      const success = await authStore.login({
        username: 'testuser',
        password: 'wrongpassword',
      });

      expect(success).toBe(false);
      expect(authStore.error).toBe('Invalid credentials');
      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(window.logService.error).toHaveBeenCalled();
    });

    it('should set loading state during login', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => {
              resolve({
                data: {
                  access_token: 'token',
                  refresh_token: 'refresh',
                  token_type: 'bearer',
                  expires_in: 1800,
                },
              });
            }, 100)
          )
      );

      apiClient.get.mockResolvedValueOnce({
        data: { id: 1, username: 'test' },
      });

      const loginPromise = authStore.login({
        username: 'test',
        password: 'pass',
      });

      expect(authStore.isLoading).toBe(true);

      await loginPromise;

      expect(authStore.isLoading).toBe(false);
    });
  });

  describe('Logout Action', () => {
    it('should logout and clear tokens', async () => {
      const authStore = useAuthStore();

      // Set up authenticated state
      authStore.accessToken = 'test_token';
      authStore.refreshToken = 'test_refresh';
      authStore.user = { username: 'test', id: 1 };

      apiClient.post.mockResolvedValueOnce({
        data: { message: 'Logged out successfully' },
      });

      await authStore.logout();

      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
      expect(window.logService.info).toHaveBeenCalledWith('User logged out');
    });

    it('should handle logout API failure gracefully', async () => {
      const authStore = useAuthStore();

      authStore.accessToken = 'test_token';
      authStore.user = { username: 'test' };

      apiClient.post.mockRejectedValueOnce(new Error('API Error'));

      await authStore.logout();

      // Should still clear local state even if API call fails
      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalled();
    });
  });

  describe('Fetch Current User Action', () => {
    it('should fetch current user successfully', async () => {
      const authStore = useAuthStore();
      authStore.accessToken = 'test_token';

      const mockUserResponse = {
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'admin',
          permissions: ['users:read', 'users:write'],
        },
      };

      apiClient.get.mockResolvedValueOnce(mockUserResponse);

      const success = await authStore.fetchCurrentUser();

      expect(success).toBe(true);
      expect(authStore.user).toEqual(mockUserResponse.data);
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });

    it('should handle fetch user failure', async () => {
      const authStore = useAuthStore();
      authStore.accessToken = 'test_token';

      apiClient.get.mockRejectedValueOnce(new Error('Unauthorized'));

      const success = await authStore.fetchCurrentUser();

      expect(success).toBe(false);
      expect(authStore.user).toBeNull();
    });
  });

  describe('Refresh Access Token Action', () => {
    it('should refresh token successfully', async () => {
      const authStore = useAuthStore();
      authStore.refreshToken = 'old_refresh_token';

      const mockResponse = {
        data: {
          access_token: 'new_access_token',
          refresh_token: 'new_refresh_token',
          token_type: 'bearer',
          expires_in: 1800,
        },
      };

      apiClient.post.mockResolvedValueOnce(mockResponse);

      const success = await authStore.refreshAccessToken();

      expect(success).toBe(true);
      expect(authStore.accessToken).toBe('new_access_token');
      expect(authStore.refreshToken).toBe('new_refresh_token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('access_token', 'new_access_token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'new_refresh_token');
    });

    it('should handle refresh token failure and logout', async () => {
      const authStore = useAuthStore();
      authStore.refreshToken = 'invalid_refresh_token';
      authStore.accessToken = 'old_token';
      authStore.user = { username: 'test' };

      apiClient.post.mockRejectedValueOnce(new Error('Invalid refresh token'));

      const success = await authStore.refreshAccessToken();

      expect(success).toBe(false);
      // Should clear auth state on refresh failure
      expect(authStore.accessToken).toBeNull();
      expect(authStore.refreshToken).toBeNull();
      expect(authStore.user).toBeNull();
    });
  });

  describe('Change Password Action', () => {
    it('should change password successfully', async () => {
      const authStore = useAuthStore();

      apiClient.post.mockResolvedValueOnce({
        data: { message: 'Password changed successfully' },
      });

      const success = await authStore.changePassword({
        current_password: 'oldpass',
        new_password: 'newpass',
      });

      expect(success).toBe(true);
      expect(authStore.error).toBeNull();
      expect(apiClient.post).toHaveBeenCalledWith('/auth/change-password', {
        current_password: 'oldpass',
        new_password: 'newpass',
      });
    });

    it('should handle password change failure', async () => {
      const authStore = useAuthStore();

      const mockError = {
        response: {
          data: {
            detail: 'Current password is incorrect',
          },
        },
      };

      apiClient.post.mockRejectedValueOnce(mockError);

      const success = await authStore.changePassword({
        current_password: 'wrongpass',
        new_password: 'newpass',
      });

      expect(success).toBe(false);
      expect(authStore.error).toBe('Current password is incorrect');
    });
  });

  describe('Initialize Action', () => {
    it('should initialize and fetch user if token exists', async () => {
      localStorageMock.setItem('access_token', 'existing_token');

      const mockUserResponse = {
        data: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com',
          role: 'viewer',
        },
      };

      apiClient.get.mockResolvedValueOnce(mockUserResponse);

      const authStore = useAuthStore();
      await authStore.initialize();

      expect(authStore.user).toEqual(mockUserResponse.data);
      expect(apiClient.get).toHaveBeenCalledWith('/auth/me');
    });

    it('should not fetch user if no token exists', async () => {
      const authStore = useAuthStore();
      await authStore.initialize();

      expect(apiClient.get).not.toHaveBeenCalled();
      expect(authStore.user).toBeNull();
    });

    it('should clear tokens if user fetch fails during initialization', async () => {
      localStorageMock.setItem('access_token', 'invalid_token');

      apiClient.get.mockRejectedValueOnce(new Error('Unauthorized'));

      const authStore = useAuthStore();
      await authStore.initialize();

      expect(authStore.accessToken).toBeNull();
      expect(authStore.user).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    });
  });

  describe('Permission Checks', () => {
    it('should check if user has specific permission', () => {
      const authStore = useAuthStore();

      authStore.user = {
        permissions: ['phenopackets:read', 'variants:write', 'users:delete'],
      };

      expect(authStore.userPermissions).toContain('phenopackets:read');
      expect(authStore.userPermissions).toContain('variants:write');
      expect(authStore.userPermissions).not.toContain('system:manage');
    });
  });

  describe('Error Handling', () => {
    it('should clear error when starting new login', async () => {
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
  });
});
