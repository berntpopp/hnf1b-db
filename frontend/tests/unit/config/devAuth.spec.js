import { afterEach, describe, expect, it } from 'vitest';

import {
  getDevQuickLoginBackendUnavailableMessage,
  getDevQuickLoginDisabledMessage,
  isDevQuickLoginEnabled,
} from '@/config/devAuth';

describe('devAuth config helpers', () => {
  const originalDev = import.meta.env.DEV;
  const originalFlag = import.meta.env.VITE_ENABLE_DEV_AUTH;

  afterEach(() => {
    import.meta.env.DEV = originalDev;
    import.meta.env.VITE_ENABLE_DEV_AUTH = originalFlag;
  });

  it('requires both dev mode and an explicit enable flag', () => {
    import.meta.env.DEV = true;
    import.meta.env.VITE_ENABLE_DEV_AUTH = 'false';
    expect(isDevQuickLoginEnabled()).toBe(false);

    import.meta.env.VITE_ENABLE_DEV_AUTH = 'true';
    expect(isDevQuickLoginEnabled()).toBe(true);

    import.meta.env.DEV = false;
    expect(isDevQuickLoginEnabled()).toBe(false);
  });

  it('accepts common truthy flag spellings', () => {
    import.meta.env.DEV = true;

    for (const value of ['1', 'true', 'TRUE', 'yes', 'On']) {
      import.meta.env.VITE_ENABLE_DEV_AUTH = value;
      expect(isDevQuickLoginEnabled()).toBe(true);
    }
  });

  it('returns user-facing misconfiguration messages', () => {
    expect(getDevQuickLoginDisabledMessage()).toContain('VITE_ENABLE_DEV_AUTH');
    expect(getDevQuickLoginBackendUnavailableMessage()).toContain('ENABLE_DEV_AUTH=true');
  });
});
