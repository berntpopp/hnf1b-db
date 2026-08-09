import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGet, mockPatch, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPatch: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('@/api/transport', () => ({
  apiClient: { get: mockGet, patch: mockPatch, post: mockPost },
}));

import {
  appendCurationCorrection,
  appendCurationResolution,
  getCurationLedger,
  previewCurationProjection,
  saveReportObservation,
} from '@/api/domain/curation';

describe('curation API domain helper', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads the private observation ledger', async () => {
    await getCurationLedger('PP-317');
    expect(mockGet).toHaveBeenCalledWith('/phenopackets/PP-317/curation');
  });

  it('previews one complete observation without writing', async () => {
    const observation = { observationId: 'report-1', publication: { doi: '10.1/example' } };
    await previewCurationProjection('PP-317', observation);
    expect(mockPost).toHaveBeenCalledWith(
      '/phenopackets/PP-317/curation/preview',
      { observation },
      undefined
    );
  });

  it('saves one report with a strong If-Match precondition', async () => {
    const observation = { observationId: 'report/one' };
    await saveReportObservation('PP 317', observation, 7, 'Reviewed source evidence.');

    expect(mockPatch).toHaveBeenCalledWith(
      '/phenopackets/PP%20317/reports/report%2Fone',
      { observation, changeReason: 'Reviewed source evidence.' },
      { headers: { 'If-Match': '"7"' } }
    );
  });

  it('appends corrections and resolutions without replacing ledger history', async () => {
    const correction = {
      jsonPointer: '/observationsById/report-1/variant/reported/value',
      preimage: 'old',
      postimage: 'new',
      reason: 'Correct normalization.',
    };
    const resolution = {
      conflictKey: 'subject:sex',
      candidateSetDigest: 'sha256:current',
      strategy: 'select_observations',
      selectedObservationIds: ['report-1'],
      reason: 'Use the directly observed report.',
    };

    await appendCurationCorrection('PP-317', correction, 8);
    await appendCurationResolution('PP-317', resolution, 9);

    expect(mockPost).toHaveBeenNthCalledWith(
      1,
      '/phenopackets/PP-317/curation/corrections',
      correction,
      { headers: { 'If-Match': '"8"' } }
    );
    expect(mockPost).toHaveBeenNthCalledWith(
      2,
      '/phenopackets/PP-317/curation/resolutions',
      resolution,
      { headers: { 'If-Match': '"9"' } }
    );
  });
});
