/**
 * session.spec.js — tab-scoped token session tests for src/api/session.js
 *
 * Verifies tokens are cached in memory, persisted to sessionStorage for the
 * lifetime of the browser tab, and legacy localStorage keys are purged.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('session — tab-scoped token session', () => {
  let clearTokens;
  let getAccessToken;
  let getRefreshToken;
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
    ({ clearTokens, getAccessToken, getRefreshToken, persistTokens } =
      await import('@/api/session'));
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

    await loadSessionModule();
  });

  it('starts empty when the current tab has no stored tokens', () => {
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(sessionStorageMock.getItem).toHaveBeenCalledWith('access_token');
    expect(sessionStorageMock.getItem).toHaveBeenCalledWith('refresh_token');
  });

  it('purges legacy localStorage token keys during module initialization', async () => {
    await loadSessionModule();

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
  });

  it('persists tokens in memory and sessionStorage', () => {
    persistTokens({ accessToken: 'a-tok', refreshToken: 'r-tok' });

    expect(getAccessToken()).toBe('a-tok');
    expect(getRefreshToken()).toBe('r-tok');
    expect(sessionStorageMock.setItem).toHaveBeenCalledWith('access_token', 'a-tok');
    expect(sessionStorageMock.setItem).toHaveBeenCalledWith('refresh_token', 'r-tok');
  });

  it('overwrites existing tokens on re-persist', () => {
    persistTokens({ accessToken: 'old-a', refreshToken: 'old-r' });
    persistTokens({ accessToken: 'new-a', refreshToken: 'new-r' });

    expect(getAccessToken()).toBe('new-a');
    expect(getRefreshToken()).toBe('new-r');
  });

  it('clears tokens from memory, sessionStorage, and legacy localStorage keys', () => {
    persistTokens({ accessToken: 'a', refreshToken: 'r' });

    localStorageMock.removeItem.mockClear();
    sessionStorageMock.removeItem.mockClear();
    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('refresh_token');
  });

  it('restores tokens from sessionStorage on module load', async () => {
    vi.resetModules();
    sessionStorageMock.getItem.mockImplementation((key) => {
      if (key === 'access_token') return 'saved-access';
      if (key === 'refresh_token') return 'saved-refresh';
      return null;
    });

    await loadSessionModule();

    expect(getAccessToken()).toBe('saved-access');
    expect(getRefreshToken()).toBe('saved-refresh');
  });
});
