/**
 * session.spec.js — In-memory token session tests for src/api/session.js
 *
 * Verifies tokens live only in module memory and that localStorage is
 * not consulted or mutated.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getAccessToken, getRefreshToken, persistTokens, clearTokens } from '@/api/session';

describe('session — in-memory token session', () => {
  const localStorageMock = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };

  beforeEach(() => {
    clearTokens();
    vi.clearAllMocks();

    Object.defineProperty(globalThis, 'localStorage', {
      value: localStorageMock,
      writable: true,
      configurable: true,
    });
  });

  it('starts empty and ignores stale localStorage entries', () => {
    localStorageMock.getItem.mockReturnValueOnce('stale-access');
    localStorageMock.getItem.mockReturnValueOnce('stale-refresh');

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(localStorageMock.getItem).not.toHaveBeenCalled();
  });

  it('persists tokens only in memory', () => {
    persistTokens({ accessToken: 'a-tok', refreshToken: 'r-tok' });

    expect(getAccessToken()).toBe('a-tok');
    expect(getRefreshToken()).toBe('r-tok');
    expect(localStorageMock.setItem).not.toHaveBeenCalled();
  });

  it('overwrites existing in-memory tokens on re-persist', () => {
    persistTokens({ accessToken: 'old-a', refreshToken: 'old-r' });
    persistTokens({ accessToken: 'new-a', refreshToken: 'new-r' });

    expect(getAccessToken()).toBe('new-a');
    expect(getRefreshToken()).toBe('new-r');
  });

  it('clears tokens from memory without touching localStorage', () => {
    persistTokens({ accessToken: 'a', refreshToken: 'r' });

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(localStorageMock.removeItem).not.toHaveBeenCalled();
  });
});
