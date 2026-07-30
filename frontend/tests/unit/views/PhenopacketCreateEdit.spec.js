/**
 * Regression tests for PhenopacketCreateEdit.vue.
 *
 * `publications` is editor-only component state, never a key on `phenopacket`:
 * it is not a Phenopackets v2 field, and buildSubmissionPhenopacket spreads
 * `phenopacket` wholesale into the save payload. PMIDs are promoted to
 * `metaData.externalReferences` on save and read back the same way on load.
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
    publications: [],
    phenopacket: {
      id: 'PP-001',
      subject: { id: 'SUB-001', sex: 'UNKNOWN_SEX' },
      phenotypicFeatures: [],
      interpretations: [],
      metaData: { externalReferences: [] },
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

  it('loads PMID publications into component state', async () => {
    getPhenopacket.mockResolvedValueOnce({ data: phenopacketResponse });
    const ctx = createContext();

    await PhenopacketCreateEdit.methods.loadPhenopacket.call(ctx);

    expect(ctx.publications).toEqual([{ pmid: '12345678' }]);
    expect(ctx.loading).toBe(false);
    expect(ctx.revision).toBe(7);
    expect(ctx.savedRecordState).toBe('draft');
  });

  it('submits PMID publications as backend-consumable externalReferences', async () => {
    updatePhenopacket.mockResolvedValueOnce({
      data: { phenopacket_id: 'PP-001' },
    });
    const ctx = createContext({
      publications: [{ pmid: '12345678' }],
      phenopacket: {
        id: 'PP-001',
        subject: {
          id: 'SUB-001',
          sex: 'UNKNOWN_SEX',
        },
        phenotypicFeatures: [{ id: 'HP:0000001' }],
        interpretations: [],
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
      phenopacket: expect.not.objectContaining({ publications: expect.anything() }),
      revision: 7,
      change_reason: 'Updated publication list',
    });

    const submitted = updatePhenopacket.mock.calls[0][1].phenopacket;
    expect(submitted.metaData.externalReferences).toEqual([{ id: 'PMID:12345678' }]);
  });

  it('normalizes PMID publications into metaData.externalReferences and preserves other refs', async () => {
    updatePhenopacket.mockResolvedValueOnce({
      data: { phenopacket_id: 'PP-001' },
    });
    const ctx = createContext({
      publications: [{ pmid: '12345678' }],
      phenopacket: {
        id: 'PP-001',
        subject: {
          id: 'SUB-001',
          sex: 'UNKNOWN_SEX',
        },
        phenotypicFeatures: [{ id: 'HP:0000001' }],
        interpretations: [],
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
      phenopacket: expect.not.objectContaining({ publications: expect.anything() }),
      revision: 7,
      change_reason: 'Updated publication list',
    });

    const submitted = updatePhenopacket.mock.calls[0][1].phenopacket;
    expect(submitted.metaData.externalReferences).toEqual([
      { id: 'DOI:10.1000/example' },
      { id: 'PMID:12345678' },
    ]);
  });
});

describe('buildSubmissionPhenopacket', () => {
  const build = PhenopacketCreateEdit.methods.buildSubmissionPhenopacket;

  it('never emits a top-level publications key', () => {
    const out = build.call(createContext({ publications: [{ pmid: '25324567' }] }));
    expect(out).not.toHaveProperty('publications');
  });

  it('strips a legacy publications key that arrives on a loaded record', () => {
    // Records saved before this fix carry the key inside the stored document.
    // Loading and re-saving one must not perpetuate it.
    const ctx = createContext({ publications: [{ pmid: '25324567' }] });
    ctx.phenopacket.publications = [{ pmid: 'stale' }];

    expect(build.call(ctx)).not.toHaveProperty('publications');
  });

  it('promotes PMIDs to metaData.externalReferences in order', () => {
    const out = build.call(
      createContext({ publications: [{ pmid: '25324567' }, { pmid: '20378641' }] })
    );
    expect(out.metaData.externalReferences).toEqual([
      { id: 'PMID:25324567' },
      { id: 'PMID:20378641' },
    ]);
  });

  it('drops blank PMID rows', () => {
    const out = build.call(createContext({ publications: [{ pmid: '  ' }, { pmid: '25324567' }] }));
    expect(out.metaData.externalReferences).toEqual([{ id: 'PMID:25324567' }]);
  });
});
