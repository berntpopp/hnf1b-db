/**
 * session.spec.js — Token storage contract tests for src/api/session.js
 *
 * Verifies localStorage round-trips, partial persistence, clearTokens,
 * and absent-token handling.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { getAccessToken, getRefreshToken, persistTokens, clearTokens } from '@/api/session';

describe('session — token storage contract', () => {
  /** @type {Record<string, string>} */
  let store;

  beforeEach(() => {
    store = {};
    // Provide a minimal localStorage stub for happy-dom
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (key) => store[key] ?? null,
        setItem: (key, value) => {
          store[key] = String(value);
        },
        removeItem: (key) => {
          delete store[key];
        },
        clear: () => {
          store = {};
        },
      },
      writable: true,
      configurable: true,
    });
  });

  it('returns null when no tokens are stored', () => {
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('round-trips both tokens through persistTokens', () => {
    persistTokens({ accessToken: 'a-tok', refreshToken: 'r-tok' });
    expect(getAccessToken()).toBe('a-tok');
    expect(getRefreshToken()).toBe('r-tok');
  });

  it('persists only the accessToken when refreshToken is omitted', () => {
    persistTokens({ accessToken: 'a-only' });
    expect(getAccessToken()).toBe('a-only');
    expect(getRefreshToken()).toBeNull();
  });

  it('persists only the refreshToken when accessToken is omitted', () => {
    persistTokens({ refreshToken: 'r-only' });
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBe('r-only');
  });

  it('clearTokens removes both tokens', () => {
    persistTokens({ accessToken: 'a', refreshToken: 'r' });
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('clearTokens is safe when no tokens exist', () => {
    // Should not throw
    clearTokens();
    expect(getAccessToken()).toBeNull();
  });

  it('overwrites existing tokens on re-persist', () => {
    persistTokens({ accessToken: 'old-a', refreshToken: 'old-r' });
    persistTokens({ accessToken: 'new-a', refreshToken: 'new-r' });
    expect(getAccessToken()).toBe('new-a');
    expect(getRefreshToken()).toBe('new-r');
  });
});
