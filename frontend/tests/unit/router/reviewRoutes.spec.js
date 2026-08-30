import { beforeEach, describe, expect, it, vi } from 'vitest';

import { resolveRouteAccess, routes } from '@/router';

const from = { path: '/phenopackets', fullPath: '/phenopackets' };

const routeByName = (name) => routes.find((route) => route.name === name);

const makeStore = ({
  accessToken = 'token',
  hasInitialized = true,
  user = { role: 'curator' },
  initialize = vi.fn(),
  fetchCurrentUser = vi.fn(),
} = {}) => ({
  accessToken,
  hasInitialized,
  user,
  initialize,
  fetchCurrentUser,
});

describe('review and curator route access', () => {
  beforeEach(() => {
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('marks review routes as curator-only authenticated surfaces', () => {
    expect(routeByName('ReviewQueue')?.meta).toMatchObject({
      requiresAuth: true,
      requiresCurator: true,
    });
    expect(routeByName('PhenopacketReview')?.meta).toMatchObject({
      requiresAuth: true,
      requiresCurator: true,
    });
  });

  it('marks create and edit routes as curator-only authenticated surfaces', () => {
    expect(routeByName('CreatePhenopacket')?.meta).toMatchObject({
      requiresAuth: true,
      requiresCurator: true,
    });
    expect(routeByName('EditPhenopacket')?.meta).toMatchObject({
      requiresAuth: true,
      requiresCurator: true,
    });
  });

  it('redirects an anonymous review route visitor to login with the original return URL', async () => {
    const authStore = makeStore({
      accessToken: null,
      hasInitialized: false,
      user: null,
      initialize: vi.fn().mockResolvedValue(undefined),
    });

    const result = await resolveRouteAccess(
      {
        name: 'ReviewQueue',
        path: '/review',
        fullPath: '/review?filter%5Bstate%5D=in_review',
        meta: { requiresAuth: true, requiresCurator: true },
      },
      from,
      authStore
    );

    expect(authStore.initialize).toHaveBeenCalledTimes(1);
    expect(result).toEqual({
      name: 'Login',
      query: { redirect: '/review?filter%5Bstate%5D=in_review' },
    });
  });

  it('returns NotFound for a viewer without disclosing the review record', async () => {
    const reviewRoute = {
      name: 'PhenopacketReview',
      path: '/review/PP-317',
      fullPath: '/review/PP-317',
      meta: { requiresAuth: true, requiresCurator: true },
    };

    expect(
      await resolveRouteAccess(reviewRoute, from, makeStore({ user: { role: 'viewer' } }))
    ).toEqual({ name: 'NotFound' });
  });

  it('returns NotFound for a viewer on create and edit forms', async () => {
    const viewerStore = makeStore({ user: { role: 'viewer' } });

    await expect(
      resolveRouteAccess(
        {
          name: 'CreatePhenopacket',
          path: '/phenopackets/create',
          fullPath: '/phenopackets/create',
          meta: { requiresAuth: true, requiresCurator: true },
        },
        from,
        viewerStore
      )
    ).resolves.toEqual({ name: 'NotFound' });
    await expect(
      resolveRouteAccess(
        {
          name: 'EditPhenopacket',
          path: '/phenopackets/PP-317/edit',
          fullPath: '/phenopackets/PP-317/edit',
          meta: { requiresAuth: true, requiresCurator: true },
        },
        from,
        viewerStore
      )
    ).resolves.toEqual({ name: 'NotFound' });
  });

  it.each([
    ['CreatePhenopacket', '/phenopackets/create'],
    ['EditPhenopacket', '/phenopackets/PP-317/edit'],
  ])('preserves the exact anonymous return URL for %s', async (name, fullPath) => {
    const authStore = makeStore({
      accessToken: null,
      hasInitialized: false,
      user: null,
      initialize: vi.fn().mockResolvedValue(undefined),
    });

    await expect(
      resolveRouteAccess(
        {
          name,
          path: fullPath,
          fullPath: `${fullPath}?from=registry`,
          meta: { requiresAuth: true, requiresCurator: true },
        },
        from,
        authStore
      )
    ).resolves.toEqual({
      name: 'Login',
      query: { redirect: `${fullPath}?from=registry` },
    });
  });

  it.each(['curator', 'admin'])('allows %s users to open create and edit forms', async (role) => {
    for (const [name, fullPath] of [
      ['CreatePhenopacket', '/phenopackets/create'],
      ['EditPhenopacket', '/phenopackets/PP-317/edit'],
    ]) {
      await expect(
        resolveRouteAccess(
          {
            name,
            path: fullPath,
            fullPath,
            meta: { requiresAuth: true, requiresCurator: true },
          },
          from,
          makeStore({ user: { role } })
        )
      ).resolves.toBeUndefined();
    }
  });

  it.each(['curator', 'admin'])('allows %s users to open review routes', async (role) => {
    const result = await resolveRouteAccess(
      {
        name: 'ReviewQueue',
        path: '/review',
        fullPath: '/review',
        meta: { requiresAuth: true, requiresCurator: true },
      },
      from,
      makeStore({ user: { role } })
    );

    expect(result).toBeUndefined();
  });

  it('keeps admin-only routes redirected to Home for non-admin curators', async () => {
    const result = await resolveRouteAccess(
      {
        name: 'AdminDashboard',
        path: '/admin',
        fullPath: '/admin',
        meta: { requiresAuth: true, requiresAdmin: true },
      },
      from,
      makeStore({ user: { role: 'curator' } })
    );

    expect(result).toEqual({ name: 'Home' });
  });
});
