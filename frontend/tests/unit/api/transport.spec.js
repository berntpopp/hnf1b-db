/**
 * transport.spec.js — Thunder-herd guard test for src/api/transport.js
 *
 * Fires N concurrent requests that all receive 401, then asserts that
 * the refresh endpoint is called exactly once (the queue coalesces).
 *
 * Uses vi.mock to intercept axios and the auth store without any extra
 * dependencies (no axios-mock-adapter needed).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mocks — must be declared before importing the module under test
// ---------------------------------------------------------------------------

// Track interceptors registered by transport.js
let requestInterceptorFulfill;
let _requestInterceptorReject;
let _responseInterceptorFulfill;
let responseInterceptorReject;

// Mock axios — capture interceptors and provide a callable client
const mockAxiosInstance = vi.fn();
mockAxiosInstance.interceptors = {
  request: {
    use: vi.fn((fulfill, reject) => {
      requestInterceptorFulfill = fulfill;
      _requestInterceptorReject = reject;
    }),
  },
  response: {
    use: vi.fn((fulfill, reject) => {
      _responseInterceptorFulfill = fulfill;
      responseInterceptorReject = reject;
    }),
  },
};
mockAxiosInstance.get = vi.fn();
mockAxiosInstance.post = vi.fn();
mockAxiosInstance.defaults = { headers: { common: {} } };

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

// Mock session — so the request interceptor can read the access token
vi.mock('@/api/session', () => ({
  getAccessToken: vi.fn(() => 'initial-token'),
  clearTokens: vi.fn(),
}));

// Mock auth store — refreshAccessToken resolves with a new token
const mockRefreshAccessToken = vi.fn();
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    refreshAccessToken: mockRefreshAccessToken,
  }),
}));

// Provide window.logService stub
beforeEach(() => {
  globalThis.window = globalThis.window || {};
  globalThis.window.logService = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  };
  globalThis.window.location = { pathname: '/somewhere', href: '' };
});

describe('transport — refresh-queue thunder-herd guard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefreshAccessToken.mockResolvedValue('fresh-token');

    // When apiClient retries a request, resolve it successfully
    mockAxiosInstance.mockResolvedValue({ data: { ok: true } });
  });

  it('registers request and response interceptors', async () => {
    // Dynamic import so mocks are in place first
    await import('@/api/transport');

    expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalledOnce();
    expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalledOnce();
  });

  it('request interceptor attaches Bearer token from session', async () => {
    await import('@/api/transport');

    const config = { headers: {} };
    const result = requestInterceptorFulfill(config);
    expect(result.headers.Authorization).toBe('Bearer initial-token');
  });

  it('coalesces 5 concurrent 401s into a single refresh call', async () => {
    await import('@/api/transport');

    // Build 5 "401 error" objects with distinct configs
    const errors = Array.from({ length: 5 }, (_, i) => ({
      config: {
        url: `/phenopackets/${i}`,
        headers: {},
        _retry: false,
      },
      response: {
        status: 401,
        data: { detail: 'Token expired' },
      },
      message: 'Request failed with status code 401',
    }));

    // Fire all 5 through the response error interceptor concurrently
    const promises = errors.map((err) => responseInterceptorReject(err));

    // Wait for all to settle
    const results = await Promise.allSettled(promises);

    // All should have resolved (retried successfully)
    results.forEach((r) => {
      expect(r.status).toBe('fulfilled');
    });

    // The refresh function should have been called exactly ONCE
    expect(mockRefreshAccessToken).toHaveBeenCalledTimes(1);
  });

  it('skips refresh for auth login endpoint', async () => {
    await import('@/api/transport');

    const error = {
      config: { url: '/auth/login', headers: {}, _retry: false },
      response: { status: 401, data: { detail: 'Bad credentials' } },
      message: 'Request failed with status code 401',
    };

    await expect(responseInterceptorReject(error)).rejects.toBeTruthy();
    expect(mockRefreshAccessToken).not.toHaveBeenCalled();
  });

  it('skips refresh for auth refresh endpoint', async () => {
    await import('@/api/transport');

    const error = {
      config: { url: '/auth/refresh', headers: {}, _retry: false },
      response: { status: 401, data: { detail: 'Refresh expired' } },
      message: 'Request failed with status code 401',
    };

    await expect(responseInterceptorReject(error)).rejects.toBeTruthy();
    expect(mockRefreshAccessToken).not.toHaveBeenCalled();
  });

  it('rejects queued requests when refresh fails', async () => {
    await import('@/api/transport');

    mockRefreshAccessToken.mockRejectedValue(new Error('Refresh failed'));

    const errors = Array.from({ length: 3 }, (_, i) => ({
      config: { url: `/data/${i}`, headers: {}, _retry: false },
      response: { status: 401, data: { detail: 'Token expired' } },
      message: 'Request failed with status code 401',
    }));

    const promises = errors.map((err) => responseInterceptorReject(err));
    const results = await Promise.allSettled(promises);

    // All should be rejected
    results.forEach((r) => {
      expect(r.status).toBe('rejected');
    });

    // Still only one refresh attempt
    expect(mockRefreshAccessToken).toHaveBeenCalledTimes(1);
    const { clearTokens } = await import('@/api/session');
    expect(clearTokens).toHaveBeenCalledOnce();
  });
});
