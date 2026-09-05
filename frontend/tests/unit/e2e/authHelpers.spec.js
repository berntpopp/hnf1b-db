import { afterEach, describe, expect, it, vi } from 'vitest';

import * as authHelpers from '@/../tests/e2e/helpers/auth.js';

const { apiLogin } = authHelpers;

afterEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

describe('e2e auth helpers', () => {
  it('uses two distinct deterministic curator principals by default', async () => {
    vi.stubEnv('E2E_CURATOR_A_USERNAME', '');
    vi.stubEnv('E2E_CURATOR_A_PASSWORD', '');
    vi.stubEnv('E2E_CURATOR_B_USERNAME', '');
    vi.stubEnv('E2E_CURATOR_B_PASSWORD', '');
    const calls = [];
    const req = {
      post: vi.fn(async (_url, options) => {
        calls.push(options.data);
        return {
          ok: () => true,
          json: async () => ({ access_token: `token-${options.data.username}` }),
          headersArray: () => [
            { name: 'set-cookie', value: 'refresh_token=refresh-value; Path=/api/v2; HttpOnly' },
            { name: 'set-cookie', value: 'csrf_token=csrf-value; Path=/' },
          ],
        };
      }),
    };

    await authHelpers.loginAsCuratorA(req, 'http://localhost:8000/api/v2');
    await authHelpers.loginAsCuratorB(req, 'http://localhost:8000/api/v2');

    expect(calls).toEqual([
      { username: 'dev-curator-a', password: 'DevCuratorA!2026' },
      { username: 'dev-curator-b', password: 'DevCuratorB!2026' },
    ]);
  });

  it.each(['A', 'B'])('rejects a partial explicit curator %s credential pair', async (actor) => {
    vi.stubEnv(`E2E_CURATOR_${actor}_USERNAME`, `explicit-curator-${actor.toLowerCase()}`);
    vi.stubEnv(`E2E_CURATOR_${actor}_PASSWORD`, '');
    const req = { post: vi.fn() };

    await expect(
      authHelpers[`loginAsCurator${actor}`](req, 'http://localhost:8000/api/v2')
    ).rejects.toThrow(`E2E_CURATOR_${actor}_USERNAME and E2E_CURATOR_${actor}_PASSWORD`);
    expect(req.post).not.toHaveBeenCalled();
  });

  it.each(['A', 'B'])('uses only the explicit curator %s credential pair', async (actor) => {
    vi.stubEnv(`E2E_CURATOR_${actor}_USERNAME`, `explicit-curator-${actor.toLowerCase()}`);
    vi.stubEnv(`E2E_CURATOR_${actor}_PASSWORD`, `Explicit${actor}!Password2026`);
    const req = {
      post: vi.fn().mockResolvedValue({
        ok: () => true,
        json: async () => ({ access_token: 'access-token' }),
        headersArray: () => [
          { name: 'set-cookie', value: 'refresh_token=refresh-value; Path=/api/v2; HttpOnly' },
          { name: 'set-cookie', value: 'csrf_token=csrf-value; Path=/' },
        ],
      }),
    };

    await authHelpers[`loginAsCurator${actor}`](req, 'http://localhost:8000/api/v2');

    expect(req.post).toHaveBeenCalledWith('http://localhost:8000/api/v2/auth/login', {
      data: {
        username: `explicit-curator-${actor.toLowerCase()}`,
        password: `Explicit${actor}!Password2026`,
      },
    });
  });

  it('keeps loginAsReviewer as a direct alias for the curator B fallback', async () => {
    vi.stubEnv('E2E_CURATOR_B_USERNAME', '');
    vi.stubEnv('E2E_CURATOR_B_PASSWORD', '');
    vi.stubEnv('E2E_REVIEWER_USERNAME', '');
    vi.stubEnv('E2E_REVIEWER_PASSWORD', '');
    const req = {
      post: vi.fn().mockResolvedValue({
        ok: () => true,
        json: async () => ({ access_token: 'reviewer-token' }),
        headersArray: () => [
          { name: 'set-cookie', value: 'refresh_token=refresh-value; Path=/api/v2; HttpOnly' },
          { name: 'set-cookie', value: 'csrf_token=csrf-value; Path=/' },
        ],
      }),
    };

    await authHelpers.loginAsReviewer(req, 'http://localhost:8000/api/v2');

    expect(req.post).toHaveBeenCalledWith('http://localhost:8000/api/v2/auth/login', {
      data: { username: 'dev-curator-b', password: 'DevCuratorB!2026' },
    });
  });

  it('honors a complete legacy reviewer credential override', async () => {
    vi.stubEnv('E2E_REVIEWER_USERNAME', 'legacy-independent-reviewer');
    vi.stubEnv('E2E_REVIEWER_PASSWORD', 'LegacyReviewer!2026');
    const req = {
      post: vi.fn().mockResolvedValue({
        ok: () => true,
        json: async () => ({ access_token: 'legacy-reviewer-token' }),
        headersArray: () => [
          { name: 'set-cookie', value: 'refresh_token=refresh-value; Path=/api/v2; HttpOnly' },
          { name: 'set-cookie', value: 'csrf_token=csrf-value; Path=/' },
        ],
      }),
    };

    await authHelpers.loginAsReviewer(req, 'http://localhost:8000/api/v2');

    expect(req.post).toHaveBeenCalledWith('http://localhost:8000/api/v2/auth/login', {
      data: {
        username: 'legacy-independent-reviewer',
        password: 'LegacyReviewer!2026',
      },
    });
  });

  it.each([
    ['E2E_REVIEWER_USERNAME', 'legacy-independent-reviewer'],
    ['E2E_REVIEWER_PASSWORD', 'LegacyReviewer!2026'],
  ])('rejects a partial legacy reviewer pair before any network call (%s)', async (key, value) => {
    vi.stubEnv('E2E_REVIEWER_USERNAME', '');
    vi.stubEnv('E2E_REVIEWER_PASSWORD', '');
    vi.stubEnv(key, value);
    const req = { post: vi.fn() };

    await expect(authHelpers.loginAsReviewer(req, 'http://localhost:8000/api/v2')).rejects.toThrow(
      'E2E_REVIEWER_USERNAME and E2E_REVIEWER_PASSWORD must be set together'
    );
    expect(req.post).not.toHaveBeenCalled();
  });

  it('returns Playwright cookie objects without mixing url and path', async () => {
    const req = {
      post: vi.fn().mockResolvedValue({
        ok: () => true,
        json: async () => ({ access_token: 'access-token' }),
        headersArray: () => [
          { name: 'set-cookie', value: 'refresh_token=refresh-value; Path=/api/v2; HttpOnly' },
          { name: 'set-cookie', value: 'csrf_token=csrf-value; Path=/' },
        ],
      }),
    };

    const result = await apiLogin(req, 'http://localhost:8000/api/v2', 'admin', 'secret');

    expect(result.accessToken).toBe('access-token');
    expect(result.cookies).toEqual([
      {
        name: 'refresh_token',
        value: 'refresh-value',
        domain: 'localhost',
        path: '/api/v2',
        httpOnly: true,
      },
      {
        name: 'csrf_token',
        value: 'csrf-value',
        url: 'http://localhost:5173',
      },
    ]);
    expect(result.cookies[0]).not.toHaveProperty('url');
    expect(result.cookies[1]).not.toHaveProperty('path');
  });
});
