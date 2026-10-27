import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn(),
}));

vi.mock('@/api/transport', () => ({
  apiClient: { get: mockGet, defaults: { baseURL: '/api/v2' } },
}));

import { getReferenceGeneDnaDistances, getReferenceGeneStructureUrl } from '@/api/domain/reference';

describe('reference structure API helpers', () => {
  beforeEach(() => vi.clearAllMocks());

  it('builds the structure URL from the API base', () => {
    expect(getReferenceGeneStructureUrl('HNF1B')).toBe('/api/v2/reference/genes/HNF1B/structure');
  });

  it('fetches DNA distances once per session per gene', async () => {
    mockGet.mockResolvedValue({ data: { residues: [] } });

    await getReferenceGeneDnaDistances('HNF1B');
    await getReferenceGeneDnaDistances('HNF1B');

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith('/reference/genes/HNF1B/structure/dna-distances');
  });

  it('retries after a failed request instead of caching the error', async () => {
    mockGet.mockRejectedValueOnce(new Error('offline'));
    mockGet.mockResolvedValueOnce({ data: { residues: [] } });

    await expect(getReferenceGeneDnaDistances('XYZ')).rejects.toThrow('offline');
    await expect(getReferenceGeneDnaDistances('XYZ')).resolves.toEqual({
      data: { residues: [] },
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
