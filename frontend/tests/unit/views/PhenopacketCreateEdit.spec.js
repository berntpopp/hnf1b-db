/**
 * Regression tests for PhenopacketCreateEdit.vue.
 *
 * The edit flow must keep PMID publications in the same source of truth that
 * the template and save payload use: phenopacket.publications.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/api', () => ({
  getPhenopacket: vi.fn(),
  createPhenopacket: vi.fn(),
  updatePhenopacket: vi.fn(),
}));

import { getPhenopacket, updatePhenopacket } from '@/api';
import PhenopacketCreateEdit from '@/views/PhenopacketCreateEdit.vue';

const EDIT_ROUTE = {
  params: {
    phenopacket_id: 'PP-001',
  },
};

const phenopacketResponse = {
  phenopacket: {
    id: 'PP-001',
    subject: {
      id: 'SUB-001',
      sex: 'UNKNOWN_SEX',
    },
    phenotypicFeatures: [],
    interpretations: [],
    publications: [],
    metaData: {
      externalReferences: [{ id: 'PMID:12345678' }, { id: 'DOI:10.1000/example' }],
    },
  },
  revision: 7,
  state: 'draft',
};

function createContext(overrides = {}) {
  return {
    $route: EDIT_ROUTE,
    $router: {
      push: vi.fn(),
    },
    $refs: {
      form: {
        validate: vi.fn().mockResolvedValue({ valid: true }),
      },
    },
    loading: true,
    saving: false,
    error: null,
    formSubmitted: false,
    revision: null,
    changeReason: '',
    savedRecordState: null,
    isEditing: true,
    buildSubmissionPhenopacket: PhenopacketCreateEdit.methods.buildSubmissionPhenopacket,
    phenopacket: {
      id: 'PP-001',
      subject: {
        id: 'SUB-001',
        sex: 'UNKNOWN_SEX',
      },
      phenotypicFeatures: [],
      interpretations: [],
      publications: [],
      metaData: {
        externalReferences: [],
      },
    },
    ...overrides,
  };
}

describe('PhenopacketCreateEdit.vue', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('loads PMID publications into phenopacket.publications', async () => {
    getPhenopacket.mockResolvedValueOnce({ data: phenopacketResponse });
    const ctx = createContext();

    await PhenopacketCreateEdit.methods.loadPhenopacket.call(ctx);

    expect(ctx.phenopacket.publications).toEqual([{ pmid: '12345678' }]);
    expect(ctx.loading).toBe(false);
    expect(ctx.revision).toBe(7);
    expect(ctx.savedRecordState).toBe('draft');
  });

  it('submits PMID publications as backend-consumable externalReferences', async () => {
    updatePhenopacket.mockResolvedValueOnce({
      data: { phenopacket_id: 'PP-001' },
    });
    const ctx = createContext({
      phenopacket: {
        id: 'PP-001',
        subject: {
          id: 'SUB-001',
          sex: 'UNKNOWN_SEX',
        },
        phenotypicFeatures: [{ id: 'HP:0000001' }],
        interpretations: [],
        publications: [{ pmid: '12345678' }],
        metaData: {
          externalReferences: [],
        },
      },
      changeReason: 'Updated publication list',
      revision: 7,
      savedRecordState: 'draft',
    });

    await PhenopacketCreateEdit.methods.handleSubmit.call(ctx);

    expect(ctx.$refs.form.validate).toHaveBeenCalledTimes(1);
    expect(updatePhenopacket).toHaveBeenCalledWith('PP-001', {
      phenopacket: expect.objectContaining({
        publications: [{ pmid: '12345678' }],
        metaData: expect.objectContaining({
          externalReferences: [{ id: 'PMID:12345678' }],
        }),
      }),
      revision: 7,
      change_reason: 'Updated publication list',
    });
  });

  it('normalizes PMID publications into metaData.externalReferences and preserves other refs', async () => {
    updatePhenopacket.mockResolvedValueOnce({
      data: { phenopacket_id: 'PP-001' },
    });
    const ctx = createContext({
      phenopacket: {
        id: 'PP-001',
        subject: {
          id: 'SUB-001',
          sex: 'UNKNOWN_SEX',
        },
        phenotypicFeatures: [{ id: 'HP:0000001' }],
        interpretations: [],
        publications: [{ pmid: '12345678' }],
        metaData: {
          created: '2024-01-01T00:00:00.000Z',
          createdBy: 'HNF1B-DB Curation Interface',
          resources: [{ id: 'hp' }],
          externalReferences: [{ id: 'DOI:10.1000/example' }, { id: 'PMID:87654321' }],
        },
      },
      changeReason: 'Updated publication list',
      revision: 7,
      savedRecordState: 'draft',
    });

    await PhenopacketCreateEdit.methods.handleSubmit.call(ctx);

    expect(updatePhenopacket).toHaveBeenCalledWith('PP-001', {
      phenopacket: expect.objectContaining({
        publications: [{ pmid: '12345678' }],
        metaData: expect.objectContaining({
          externalReferences: [{ id: 'DOI:10.1000/example' }, { id: 'PMID:12345678' }],
        }),
      }),
      revision: 7,
      change_reason: 'Updated publication list',
    });
  });
});
