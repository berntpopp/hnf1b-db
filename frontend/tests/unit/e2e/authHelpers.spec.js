import { describe, expect, it, vi } from 'vitest';

import { apiLogin } from '@/../tests/e2e/helpers/auth.js';

describe('e2e auth helpers', () => {
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
