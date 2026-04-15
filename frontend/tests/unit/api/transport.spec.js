/**
 * transport.spec.js — request/refresh queue behavior for src/api/transport.js
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

let requestInterceptorFulfill;
let _requestInterceptorReject;
let _responseInterceptorFulfill;
let responseInterceptorReject;

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

const mockGetAccessToken = vi.fn(() => 'initial-token');
const mockGetCsrfToken = vi.fn(() => 'csrf-token');

vi.mock('@/api/session', () => ({
  getAccessToken: mockGetAccessToken,
  getCsrfToken: mockGetCsrfToken,
  clearTokens: vi.fn(),
}));

const mockRefreshAccessToken = vi.fn();
vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    refreshAccessToken: mockRefreshAccessToken,
  }),
}));

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

describe('transport — request auth and refresh queue', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockGetAccessToken.mockReturnValue('initial-token');
    mockGetCsrfToken.mockReturnValue('csrf-token');
    mockRefreshAccessToken.mockResolvedValue('fresh-token');
    mockAxiosInstance.mockResolvedValue({ data: { ok: true } });
  });

  it('attaches Bearer token from session', async () => {
    await import('@/api/transport');

    const config = { method: 'get', headers: {} };
    const result = requestInterceptorFulfill(config);
    expect(result.headers.Authorization).toBe('Bearer initial-token');
  });

  it('injects X-CSRF-Token on unsafe requests when the readable cookie exists', async () => {
    await import('@/api/transport');

    const config = { method: 'post', headers: {} };
    const result = requestInterceptorFulfill(config);

    expect(result.headers['X-CSRF-Token']).toBe('csrf-token');
  });

  it('marks refresh and logout requests as credentialed cookie requests', async () => {
    await import('@/api/transport');

    const refreshConfig = requestInterceptorFulfill({
      url: '/auth/refresh',
      method: 'post',
      headers: {},
    });
    const logoutConfig = requestInterceptorFulfill({
      url: '/auth/logout',
      method: 'post',
      headers: {},
    });

    expect(refreshConfig.withCredentials).toBe(true);
    expect(logoutConfig.withCredentials).toBe(true);
  });

  it('coalesces 5 concurrent 401s into a single refresh call', async () => {
    await import('@/api/transport');

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

    const promises = errors.map((err) => responseInterceptorReject(err));
    const results = await Promise.allSettled(promises);

    results.forEach((result) => {
      expect(result.status).toBe('fulfilled');
    });
    expect(mockRefreshAccessToken).toHaveBeenCalledTimes(1);
  });

  it('skips refresh for auth login, refresh, and logout endpoints', async () => {
    await import('@/api/transport');

    for (const url of ['/auth/login', '/auth/refresh', '/auth/logout']) {
      const error = {
        config: { url, headers: {}, _retry: false },
        response: { status: 401, data: { detail: 'Unauthorized' } },
        message: 'Request failed with status code 401',
      };

      await expect(responseInterceptorReject(error)).rejects.toBeTruthy();
    }

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

    results.forEach((result) => {
      expect(result.status).toBe('rejected');
    });

    const { clearTokens } = await import('@/api/session');
    expect(mockRefreshAccessToken).toHaveBeenCalledTimes(1);
    expect(clearTokens).toHaveBeenCalledOnce();
  });
});
