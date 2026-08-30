/**
 * Unit tests for usePhenopacketState composable (Wave 7 / D.1 §9.3)
 *
 * Tests cover:
 * - transitionTo happy path: loading flag lifecycle + returned value
 * - transitionTo error path: error.value set, loading reset, re-throws
 * - loadRevisions: populates revisions.value from response data array
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import { usePhenopacketState } from '@/composables/usePhenopacketState';

// Mock the API domain module so no real HTTP calls are made.
vi.mock('@/api/domain/phenopackets', () => ({
  transitionPhenopacket: vi.fn(),
  fetchRevisions: vi.fn(),
  getPhenopacketAuditHistory: vi.fn(),
}));

import {
  transitionPhenopacket,
  fetchRevisions,
  getPhenopacketAuditHistory,
} from '@/api/domain/phenopackets';

const PHENOPACKET_ID = 'test-pp-001';

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe('usePhenopacketState', () => {
  it('resets record state synchronously and ignores stale work when the reactive id changes', async () => {
    const phenopacketId = ref('PP-001');
    const staleRevisions = deferred();
    const staleHistoryRevisions = deferred();
    const staleHistoryAudit = deferred();

    fetchRevisions.mockImplementation((id, options) => {
      if (id === 'PP-001' && options?.kind === 'revisions') return staleRevisions.promise;
      if (id === 'PP-001') return staleHistoryRevisions.promise;
      return Promise.resolve({
        data: {
          data: [
            {
              id: 22,
              revision_number: 2,
              state: 'in_review',
              actor_username: 'curator.two',
              created_at: '2026-08-30T12:00:00Z',
              change_reason: 'New record history',
            },
          ],
        },
      });
    });
    getPhenopacketAuditHistory.mockImplementation((id) => {
      if (id === 'PP-001') return staleHistoryAudit.promise;
      return Promise.resolve({ data: [] });
    });

    const state = usePhenopacketState(phenopacketId);
    const oldRevisionLoad = state.loadRevisions({ kind: 'revisions' });
    const oldHistoryLoad = state.loadHistory();

    expect(state.loading.value).toBe(true);
    expect(state.historyLoading.value).toBe(true);

    phenopacketId.value = 'PP-002';

    expect(state.revisions.value).toEqual([]);
    expect(state.historyEntries.value).toEqual([]);
    expect(state.loading.value).toBe(false);
    expect(state.error.value).toBe(null);
    expect(state.historyLoading.value).toBe(false);
    expect(state.historyError.value).toBe(null);

    await state.loadHistory();
    expect(fetchRevisions).toHaveBeenCalledWith('PP-002', undefined);
    expect(getPhenopacketAuditHistory).toHaveBeenCalledWith('PP-002');
    expect(state.historyEntries.value).toHaveLength(1);
    expect(state.historyEntries.value[0].id).toBe('22');

    staleRevisions.resolve({ data: { data: [{ id: 11 }] } });
    staleHistoryRevisions.resolve({ data: { data: [{ id: 11, revision_number: 1 }] } });
    staleHistoryAudit.resolve({ data: [] });
    await Promise.all([oldRevisionLoad, oldHistoryLoad]);

    expect(state.revisions.value).toEqual([]);
    expect(state.historyEntries.value[0].id).toBe('22');
    expect(state.loading.value).toBe(false);
    expect(state.historyLoading.value).toBe(false);
  });

  describe('transitionTo', () => {
    it('happy path: loading is true during call, false after, returns API data', async () => {
      const responseData = { phenopacket: { id: PHENOPACKET_ID }, revision: 2 };
      transitionPhenopacket.mockResolvedValueOnce({ data: responseData });

      const { loading, error, transitionTo } = usePhenopacketState(PHENOPACKET_ID);

      expect(loading.value).toBe(false);

      const promise = transitionTo('in_review', 'Ready for review', 1);

      // loading should be true while the promise is in-flight
      expect(loading.value).toBe(true);

      const result = await promise;
      await flushPromises();

      expect(loading.value).toBe(false);
      expect(error.value).toBe(null);
      expect(result).toEqual(responseData);
      expect(transitionPhenopacket).toHaveBeenCalledWith(
        PHENOPACKET_ID,
        'in_review',
        'Ready for review',
        1
      );
    });

    it('error path: sets error.value, resets loading to false, re-throws to caller', async () => {
      const apiError = new Error('Conflict');
      apiError.response = { data: { detail: { message: 'Optimistic lock conflict' } } };
      transitionPhenopacket.mockRejectedValueOnce(apiError);

      const { loading, error, transitionTo } = usePhenopacketState(PHENOPACKET_ID);

      await expect(transitionTo('archived', 'No longer active', 3)).rejects.toThrow('Conflict');
      await flushPromises();

      expect(loading.value).toBe(false);
      // error.value picks up detail.message (object path) or falls back to e.message
      expect(error.value).toEqual({ message: 'Optimistic lock conflict' });
    });

    it('error path fallback: uses e.message when response has no detail', async () => {
      const apiError = new Error('Network Error');
      transitionPhenopacket.mockRejectedValueOnce(apiError);

      const { error, transitionTo } = usePhenopacketState(PHENOPACKET_ID);

      await expect(transitionTo('draft', 'Withdraw for editing', 5)).rejects.toThrow(
        'Network Error'
      );

      expect(error.value).toBe('Network Error');
    });

    it.each(['changes_requested', 'approved', 'published'])(
      'rejects exact review target %s without sending generic transition transport',
      async (targetState) => {
        const { loading, error, transitionTo } = usePhenopacketState(PHENOPACKET_ID);

        await expect(transitionTo(targetState, 'Unsafe generic decision', 5)).rejects.toThrow(
          'requires the review workspace'
        );

        expect(transitionPhenopacket).not.toHaveBeenCalled();
        expect(loading.value).toBe(false);
        expect(error.value).toContain('requires the review workspace');
      }
    );

    it('reads the reactive id at operation start and ignores an older completion', async () => {
      const phenopacketId = ref('PP-001');
      const staleTransition = deferred();
      transitionPhenopacket
        .mockReturnValueOnce(staleTransition.promise)
        .mockResolvedValueOnce({ data: { phenopacket: { id: 'PP-002' }, revision: 2 } });
      const { loading, error, transitionTo } = usePhenopacketState(phenopacketId);

      const oldTransition = transitionTo('draft', 'Old record transition', 1);
      phenopacketId.value = 'PP-002';
      const newResult = await transitionTo('in_review', 'New record transition', 1);

      expect(transitionPhenopacket).toHaveBeenNthCalledWith(
        2,
        'PP-002',
        'in_review',
        'New record transition',
        1
      );
      expect(newResult.phenopacket.id).toBe('PP-002');

      staleTransition.resolve({ data: { phenopacket: { id: 'PP-001' }, revision: 2 } });
      await oldTransition;

      expect(loading.value).toBe(false);
      expect(error.value).toBe(null);
    });
  });

  describe('loadRevisions', () => {
    it('populates revisions.value with the response data array', async () => {
      const revisionRows = [
        { id: 1, revision: 1, state: 'draft' },
        { id: 2, revision: 2, state: 'in_review' },
      ];
      fetchRevisions.mockResolvedValueOnce({ data: { data: revisionRows, meta: { total: 2 } } });

      const { revisions, loading, loadRevisions } = usePhenopacketState(PHENOPACKET_ID);

      expect(revisions.value).toEqual([]);

      await loadRevisions({ pageSize: 10, pageNumber: 1 });
      await flushPromises();

      expect(revisions.value).toEqual(revisionRows);
      expect(loading.value).toBe(false);
      expect(fetchRevisions).toHaveBeenCalledWith(PHENOPACKET_ID, { pageSize: 10, pageNumber: 1 });
    });
  });

  describe('loadHistory', () => {
    it('merges revision and audit payloads into normalized history rows', async () => {
      fetchRevisions.mockResolvedValueOnce({
        data: {
          data: [
            {
              id: 11,
              revision_number: 11,
              state: 'approved',
              actor_username: 'curator.alice',
              created_at: '2026-04-23T08:30:00Z',
              change_reason: 'Approved after review',
            },
          ],
        },
      });
      getPhenopacketAuditHistory.mockResolvedValueOnce({
        data: [
          {
            id: '11',
            source: 'revision',
            changed_by: 'curator.alice',
            changed_at: '2026-04-23T08:30:00Z',
            change_summary: 'Approved after review',
            state_transition: { from: 'in_review', to: 'approved' },
          },
        ],
      });

      const { historyEntries, historyLoading, historyError, loadHistory } =
        usePhenopacketState(PHENOPACKET_ID);

      await loadHistory({ pageSize: 10, pageNumber: 1 });
      await flushPromises();

      expect(fetchRevisions).toHaveBeenCalledWith(PHENOPACKET_ID, {
        pageSize: 10,
        pageNumber: 1,
      });
      expect(getPhenopacketAuditHistory).toHaveBeenCalledWith(PHENOPACKET_ID);
      expect(historyLoading.value).toBe(false);
      expect(historyError.value).toBe(null);
      expect(historyEntries.value).toEqual([
        {
          id: '11',
          revisionNumber: 11,
          state: 'approved',
          actor: 'curator.alice',
          timestamp: '2026-04-23T08:30:00Z',
          summary: 'Approved after review',
        },
      ]);
    });

    it('stores historyError and rethrows when history loading fails', async () => {
      const apiError = new Error('Audit unavailable');
      fetchRevisions.mockRejectedValueOnce(apiError);

      const { historyEntries, historyLoading, historyError, loadHistory } =
        usePhenopacketState(PHENOPACKET_ID);

      await expect(loadHistory()).rejects.toThrow('Audit unavailable');
      await flushPromises();

      expect(historyEntries.value).toEqual([]);
      expect(historyLoading.value).toBe(false);
      expect(historyError.value).toBe('Audit unavailable');
    });
  });
});
