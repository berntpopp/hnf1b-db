import { beforeEach, describe, expect, it, vi } from 'vitest';

let responseInterceptorReject;

const mockAxiosInstance = vi.fn();
mockAxiosInstance.interceptors = {
  request: {
    use: vi.fn(),
  },
  response: {
    use: vi.fn((_fulfill, reject) => {
      responseInterceptorReject = reject;
    }),
  },
};

const mockClearTokens = vi.fn();
const mockRefreshAccessToken = vi.fn();
const mockRouterPush = vi.fn();
const authState = {
  accessToken: 'expired-token',
};
const currentRoute = {
  value: {
    fullPath: '/user',
  },
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

vi.mock('@/api/session', () => ({
  clearTokens: mockClearTokens,
  getAccessToken: vi.fn(() => 'expired-token'),
  getCsrfToken: vi.fn(() => null),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({
    refreshAccessToken: mockRefreshAccessToken,
    get accessToken() {
      return authState.accessToken;
    },
  }),
}));

vi.mock('@/router', () => ({
  buildLoginLocation: (fullPath) =>
    !fullPath || fullPath === '/login'
      ? { name: 'Login' }
      : { name: 'Login', query: { redirect: fullPath } },
  default: {
    currentRoute,
    push: mockRouterPush,
  },
}));

describe('transport session expiry navigation', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    authState.accessToken = 'expired-token';
    currentRoute.value.fullPath = '/user';
    mockRefreshAccessToken.mockRejectedValue(new Error('Refresh failed'));
    globalThis.window = globalThis.window || {};
    globalThis.window.logService = {
      warn: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      debug: vi.fn(),
    };
    globalThis.window.location = {
      href: '',
      pathname: '/user',
      search: '',
      hash: '',
    };
  });

  it('navigates to login through the router after refresh fails on an authenticated page', async () => {
    await import('@/api/transport');

    await expect(
      responseInterceptorReject({
        config: { url: '/auth/me', headers: {}, _retry: false },
        response: { status: 401, data: { detail: 'Token expired' } },
        message: 'Request failed with status code 401',
      })
    ).rejects.toThrow('Refresh failed');

    expect(mockClearTokens).toHaveBeenCalledOnce();
    expect(mockRouterPush).toHaveBeenCalledWith({
      name: 'Login',
      query: { redirect: '/user' },
    });
    expect(globalThis.window.location.href).not.toContain('/login');
  });

  it('preserves the current path and query in the redirect param', async () => {
    currentRoute.value.fullPath = '/phenopackets/create?tab=review&filter=active';
    globalThis.window.location.pathname = '/phenopackets/create';
    globalThis.window.location.search = '?tab=review&filter=active';

    await import('@/api/transport');

    await expect(
      responseInterceptorReject({
        config: { url: '/phenopackets/42', headers: {}, _retry: false },
        response: { status: 401, data: { detail: 'Token expired' } },
        message: 'Request failed with status code 401',
      })
    ).rejects.toThrow('Refresh failed');

    expect(mockRouterPush).toHaveBeenCalledWith({
      name: 'Login',
      query: { redirect: '/phenopackets/create?tab=review&filter=active' },
    });
  });

  it('does not create a login redirect for anonymous refresh rejection', async () => {
    authState.accessToken = null;
    currentRoute.value.fullPath = '/about';
    globalThis.window.location.pathname = '/about';

    await import('@/api/transport');

    await expect(
      responseInterceptorReject({
        config: { url: '/publications', headers: {}, _retry: false },
        response: { status: 401, data: { detail: 'Unauthorized' } },
        message: 'Request failed with status code 401',
      })
    ).rejects.toThrow('Refresh failed');

    expect(mockClearTokens).toHaveBeenCalledOnce();
    expect(mockRouterPush).not.toHaveBeenCalled();
    expect(globalThis.window.location.href).not.toContain('/login');
  });
});
