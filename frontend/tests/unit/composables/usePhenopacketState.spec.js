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
import { usePhenopacketState } from '@/composables/usePhenopacketState';

// Mock the API domain module so no real HTTP calls are made.
vi.mock('@/api/domain/phenopackets', () => ({
  transitionPhenopacket: vi.fn(),
  fetchRevisions: vi.fn(),
}));

import { transitionPhenopacket, fetchRevisions } from '@/api/domain/phenopackets';

const PHENOPACKET_ID = 'test-pp-001';

beforeEach(() => {
  vi.resetAllMocks();
});

describe('usePhenopacketState', () => {
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

      await expect(transitionTo('approved', 'LGTM', 3)).rejects.toThrow('Conflict');
      await flushPromises();

      expect(loading.value).toBe(false);
      // error.value picks up detail.message (object path) or falls back to e.message
      expect(error.value).toEqual({ message: 'Optimistic lock conflict' });
    });

    it('error path fallback: uses e.message when response has no detail', async () => {
      const apiError = new Error('Network Error');
      transitionPhenopacket.mockRejectedValueOnce(apiError);

      const { error, transitionTo } = usePhenopacketState(PHENOPACKET_ID);

      await expect(transitionTo('published', 'Ship it', 5)).rejects.toThrow('Network Error');

      expect(error.value).toBe('Network Error');
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
});
