/**
 * session.spec.js — in-memory access token and CSRF cookie helpers
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('session — in-memory access token only', () => {
  let clearTokens;
  let getAccessToken;
  let getCsrfToken;
  let persistTokens;

  const localStorageMock = {
    removeItem: vi.fn(),
  };

  const sessionStorageMock = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  };

  async function loadSessionModule() {
    ({ clearTokens, getAccessToken, getCsrfToken, persistTokens } = await import('@/api/session'));
  }

  beforeEach(async () => {
    vi.resetModules();
    vi.clearAllMocks();

    Object.defineProperty(globalThis, 'localStorage', {
      value: localStorageMock,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'sessionStorage', {
      value: sessionStorageMock,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(globalThis, 'document', {
      value: { cookie: '' },
      writable: true,
      configurable: true,
    });

    await loadSessionModule();
  });

  it('starts with no in-memory access token and does not restore from sessionStorage', () => {
    expect(getAccessToken()).toBeNull();
    expect(sessionStorageMock.getItem).not.toHaveBeenCalled();
  });

  it('purges legacy token keys from browser storage during module initialization', async () => {
    await loadSessionModule();

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
  });

  it('persists only the access token in memory', () => {
    persistTokens({ accessToken: 'a-tok', refreshToken: 'ignored-refresh-token' });

    expect(getAccessToken()).toBe('a-tok');
    expect(sessionStorageMock.setItem).not.toHaveBeenCalled();
  });

  it('clears the in-memory token and legacy browser storage keys', () => {
    persistTokens({ accessToken: 'a' });

    localStorageMock.removeItem.mockClear();
    sessionStorageMock.removeItem.mockClear();
    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
  });

  it('reads the readable CSRF cookie value', () => {
    globalThis.document.cookie = 'theme=light; csrf_token=csrf-123; other=value';

    expect(getCsrfToken()).toBe('csrf-123');
  });

  it('returns null when the CSRF cookie is absent', () => {
    globalThis.document.cookie = 'theme=light';

    expect(getCsrfToken()).toBeNull();
  });
});
