/**
 * Verifies that a global errorHandler is configured on the Vue app.
 *
 * We cannot test main.js directly (it creates an app and mounts it),
 * so this tests the pattern by constructing a Vue app with the same
 * configurator function.
 */
import { describe, it, expect, vi } from 'vitest';
import { createApp, defineComponent } from 'vue';
import { configureErrorHandler } from '@/main-error-handler';

describe('configureErrorHandler', () => {
  it('sets app.config.errorHandler', () => {
    const logError = vi.fn();
    const app = createApp(defineComponent({ render: () => null }));
    configureErrorHandler(app, logError);
    expect(app.config.errorHandler).toBeTypeOf('function');
  });

  it('routes caught errors through the provided logger', () => {
    const logError = vi.fn();
    const app = createApp(defineComponent({ render: () => null }));
    configureErrorHandler(app, logError);

    const err = new Error('boom');
    const instance = { $: { type: { name: 'TestComponent' } } };
    app.config.errorHandler(err, instance, 'test info');

    expect(logError).toHaveBeenCalled();
    expect(logError.mock.calls[0][0]).toContain('boom');
  });
});
