/**
 * Unit tests for the useSyncTask composable
 *
 * Tests cover:
 * - Initial idle state
 * - Early-completion path (backend reports completed immediately)
 * - Polling-to-completion path (pending -> running -> completed)
 * - Error path with detail extraction from response
 * - Failed task status during polling
 * - Manual stop() clearing the polling interval
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { useSyncTask } from '@/composables/useSyncTask';

// The app uses window.logService (see CLAUDE.md: no console.log in frontend).
globalThis.window.logService = {
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
};

describe('useSyncTask', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('initial state is idle with no task', () => {
    const sync = useSyncTask({
      startFn: vi.fn(),
      statusFn: vi.fn(),
      onComplete: vi.fn(),
    });
    expect(sync.task.value).toBe(null);
    expect(sync.inProgress.value).toBe(false);
  });

  it('start() returns early if backend reports completed', async () => {
    const startFn = vi.fn(async () => ({
      data: { task_id: 't1', status: 'completed', message: 'done', items_to_process: 10 },
    }));
    const onComplete = vi.fn();
    const sync = useSyncTask({ startFn, statusFn: vi.fn(), onComplete });
    await sync.start();
    await flushPromises();
    expect(sync.inProgress.value).toBe(false);
    expect(onComplete).toHaveBeenCalled();
  });

  it('start() kicks off polling when task is pending, stops on completed', async () => {
    const startFn = vi.fn(async () => ({
      data: { task_id: 't1', status: 'pending', items_to_process: 100 },
    }));
    let pollCount = 0;
    const statusFn = vi.fn(async () => {
      pollCount += 1;
      return {
        data: {
          task_id: 't1',
          status: pollCount >= 3 ? 'completed' : 'running',
          progress: pollCount * 33,
          processed: pollCount * 33,
          total: 100,
          errors: 0,
        },
      };
    });
    const onComplete = vi.fn();
    const sync = useSyncTask({ startFn, statusFn, onComplete, pollIntervalMs: 100 });
    await sync.start();
    for (let i = 0; i < 3; i += 1) {
      await vi.advanceTimersByTimeAsync(100);
    }
    expect(sync.inProgress.value).toBe(false);
    expect(onComplete).toHaveBeenCalled();
  });

  it('start() failure calls onError', async () => {
    const err = new Error('boom');
    err.response = { data: { detail: 'rate limit' } };
    const startFn = vi.fn(async () => {
      throw err;
    });
    const onError = vi.fn();
    const sync = useSyncTask({ startFn, statusFn: vi.fn(), onComplete: vi.fn(), onError });
    await sync.start();
    expect(onError).toHaveBeenCalledWith('rate limit');
    expect(sync.inProgress.value).toBe(false);
  });

  it('polling handles failed task status', async () => {
    const startFn = vi.fn(async () => ({
      data: { task_id: 't1', status: 'pending', items_to_process: 10 },
    }));
    const statusFn = vi.fn(async () => ({
      data: {
        task_id: 't1',
        status: 'failed',
        message: 'sync task failed',
        progress: 0,
        processed: 0,
        total: 10,
        errors: 1,
      },
    }));
    const onError = vi.fn();
    const sync = useSyncTask({
      startFn,
      statusFn,
      onComplete: vi.fn(),
      onError,
      pollIntervalMs: 100,
    });
    await sync.start();
    await vi.advanceTimersByTimeAsync(100);
    expect(sync.inProgress.value).toBe(false);
    expect(onError).toHaveBeenCalledWith('sync task failed');
  });

  it('stop() clears the polling interval', async () => {
    const statusFn = vi.fn(async () => ({
      data: { status: 'running', task_id: 't1', progress: 50 },
    }));
    const sync = useSyncTask({
      startFn: vi.fn(async () => ({
        data: { task_id: 't1', status: 'pending', items_to_process: 10 },
      })),
      statusFn,
      onComplete: vi.fn(),
      pollIntervalMs: 100,
    });
    await sync.start();
    sync.stop();
    const countAfterStop = statusFn.mock.calls.length;
    await vi.advanceTimersByTimeAsync(500);
    expect(statusFn.mock.calls.length).toBe(countAfterStop);
  });
});
