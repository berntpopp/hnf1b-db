/**
 * Regression tests for PhenopacketCreateEdit.vue.
 *
 * `publications` is editor-only component state, never a key on `phenopacket`:
 * it is not a Phenopackets v2 field, and buildSubmissionPhenopacket spreads
 * `phenopacket` wholesale into the save payload. PMIDs are promoted to
 * `metaData.externalReferences` on save and read back the same way on load.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { createRouter, createWebHistory } from 'vue-router';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';

// `get` must be created via vi.hoisted -- vi.mock factories are hoisted above
// the rest of the module, so a plain `const apiGet = vi.fn()` referenced
// inside one throws "Cannot access 'apiGet' before initialization".
const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));

vi.mock('@/api', () => ({
  getPhenopacket: vi.fn(),
  createPhenopacket: vi.fn(),
  updatePhenopacket: vi.fn(),
  apiClient: { get: apiGet },
}));

// PhenotypicFeaturesSection and VariantAnnotationForm are exercised by their
// own suites and pull in unrelated dependencies (useGroupedHPO's own API
// calls, VEP annotation state). Stubbed out here so the Case-section mount
// tests below stay focused and fast.
vi.mock('@/components/PhenotypicFeaturesSection.vue', () => ({
  default: {
    name: 'PhenotypicFeaturesSection',
    props: ['modelValue', 'formSubmitted'],
    template: '<div class="mock-phenotypic-features" />',
  },
}));
vi.mock('@/components/VariantAnnotationForm.vue', () => ({
  default: {
    name: 'VariantAnnotationForm',
    props: ['modelValue', 'subjectId'],
    template: '<div class="mock-variant-annotation-form" />',
  },
}));

import { getPhenopacket, updatePhenopacket } from '@/api';
import PhenopacketCreateEdit from '@/views/PhenopacketCreateEdit.vue';
import CompletenessRail from '@/components/curation/CompletenessRail.vue';

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
    mergedExternalReferences: PhenopacketCreateEdit.methods.mergedExternalReferences,
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

describe('mergedExternalReferences', () => {
  const merge = PhenopacketCreateEdit.methods.mergedExternalReferences;

  it('merges component-local PMIDs with non-PMID references already on the phenopacket', () => {
    const ctx = createContext({
      publications: [{ pmid: '25324567' }],
      phenopacket: {
        ...createContext().phenopacket,
        metaData: { externalReferences: [{ id: 'DOI:10.1000/example' }] },
      },
    });

    expect(merge.call(ctx)).toEqual([{ id: 'DOI:10.1000/example' }, { id: 'PMID:25324567' }]);
  });

  it('drops blank PMID rows, matching buildSubmissionPhenopacket', () => {
    const ctx = createContext({ publications: [{ pmid: '  ' }, { pmid: '25324567' }] });
    expect(merge.call(ctx)).toEqual([{ id: 'PMID:25324567' }]);
  });

  it('is the single source buildSubmissionPhenopacket delegates to (no duplicated logic)', () => {
    const ctx = createContext({
      publications: [{ pmid: '25324567' }],
      phenopacket: {
        ...createContext().phenopacket,
        metaData: { externalReferences: [{ id: 'DOI:10.1000/example' }] },
      },
    });

    const merged = merge.call(ctx);
    const built = PhenopacketCreateEdit.methods.buildSubmissionPhenopacket.call(ctx);

    expect(built.metaData.externalReferences).toEqual(merged);
  });
});

describe('phenopacketForCompleteness', () => {
  const computeIt = PhenopacketCreateEdit.computed.phenopacketForCompleteness;

  it('reflects an in-progress (unsaved) PMID entry not yet promoted to metaData.externalReferences', () => {
    const ctx = createContext({
      publications: [{ pmid: '25324567' }],
      phenopacket: {
        id: 'PP-001',
        subject: { id: 'SUB-001', sex: 'UNKNOWN_SEX' },
        phenotypicFeatures: [],
        interpretations: [],
        metaData: { externalReferences: [] }, // PMID not yet promoted here
      },
    });

    const result = computeIt.call(ctx);

    expect(result.metaData.externalReferences).toEqual([{ id: 'PMID:25324567' }]);
    // The underlying phenopacket itself must not be mutated by reading this.
    expect(ctx.phenopacket.metaData.externalReferences).toEqual([]);
  });

  it('matches the raw phenopacket when there are no in-progress publications', () => {
    const ctx = createContext({ publications: [] });
    const result = computeIt.call(ctx);
    expect(result.metaData.externalReferences).toEqual(
      ctx.phenopacket.metaData.externalReferences || []
    );
  });
});

// ── Case section controls (Task 4) — full mount ────────────────────────────
// Cohort, IndividualIdentifier chips, PublicationType, FamilyHistory: the
// four NEW controls (Sex and Publication already existed). These tests mount
// the real component to prove the selects are wired to the vocabulary
// composable's refs (not a hardcoded items array) and that v-model bindings
// round-trip into the right phenopacket paths.
const VOCAB_FIXTURES = {
  '/ontology/vocabularies/sex': [
    { value: 'FEMALE', label: 'Female', description: null },
    { value: 'MALE', label: 'Male', description: null },
    { value: 'UNKNOWN_SEX', label: 'Unknown', description: null },
  ],
  '/ontology/vocabularies/cohort': [
    { value: 'born', label: 'Born', description: null },
    { value: 'fetus', label: 'Fetus', description: null },
  ],
  '/ontology/vocabularies/family-history': [
    { value: 'positive', label: 'Positive', description: null },
    { value: 'negative', label: 'Negative', description: null },
    { value: 'not_reported', label: 'Not reported', description: null },
  ],
  '/ontology/vocabularies/publication-type': [
    { value: 'case_report', label: 'Case report', description: null },
    { value: 'case_series', label: 'Case series', description: null },
  ],
  '/ontology/vocabularies/interpretation-status': [
    { value: 'PATHOGENIC', label: 'Pathogenic', description: null },
    { value: 'LIKELY_PATHOGENIC', label: 'Likely pathogenic', description: null },
  ],
  '/ontology/vocabularies/classification-system': [
    { value: 'acmg', label: 'ACMG', description: null },
    { value: 'clingen_cnv', label: 'ClinGen CNV', description: null },
  ],
};

function mockVocabularyApi() {
  apiGet.mockImplementation((url) => {
    const key = Object.keys(VOCAB_FIXTURES).find((k) => url.includes(k));
    return Promise.resolve({ data: { data: key ? VOCAB_FIXTURES[key] : [] } });
  });
}

async function mountCreateForm() {
  const vuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/phenopackets/create', name: 'CreatePhenopacket', component: PhenopacketCreateEdit },
      { path: '/phenopackets', name: 'Phenopackets', component: { template: '<div />' } },
    ],
  });
  await router.push('/phenopackets/create');
  await router.isReady();

  return mount(PhenopacketCreateEdit, {
    global: { plugins: [router, vuetify] },
  });
}

function selectByLabel(wrapper, label) {
  return wrapper.findAllComponents({ name: 'VSelect' }).find((c) => c.props('label') === label);
}

describe('Case section controls (Task 4)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('wires the Cohort select to phenopacket.hnf1bCuration.cohort using the vocabulary composable', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const cohortSelect = selectByLabel(wrapper, 'Cohort');
    expect(cohortSelect).toBeTruthy();
    // Items come from the composable's fixture response, not a literal array
    // hardcoded in the template.
    expect(cohortSelect.props('items')).toEqual(VOCAB_FIXTURES['/ontology/vocabularies/cohort']);

    await cohortSelect.vm.$emit('update:modelValue', 'born');
    expect(wrapper.vm.phenopacket.hnf1bCuration.cohort).toBe('born');
  });

  it('wires the Publication type select to phenopacket.hnf1bCuration.publicationType using the vocabulary composable', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const select = selectByLabel(wrapper, 'Publication type');
    expect(select).toBeTruthy();
    expect(select.props('items')).toEqual(
      VOCAB_FIXTURES['/ontology/vocabularies/publication-type']
    );

    await select.vm.$emit('update:modelValue', 'case_report');
    expect(wrapper.vm.phenopacket.hnf1bCuration.publicationType).toBe('case_report');
  });

  it('wires the Family history select to phenopacket.hnf1bCuration.familyHistory using the vocabulary composable', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const select = selectByLabel(wrapper, 'Family history');
    expect(select).toBeTruthy();
    expect(select.props('items')).toEqual(VOCAB_FIXTURES['/ontology/vocabularies/family-history']);

    await select.vm.$emit('update:modelValue', 'not_reported');
    expect(wrapper.vm.phenopacket.hnf1bCuration.familyHistory).toBe('not_reported');
  });

  it('round-trips individual identifiers into phenopacket.subject.alternateIds via the chips input', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const combobox = wrapper.findComponent({ name: 'VCombobox' });
    expect(combobox.exists()).toBe(true);
    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual([]);

    // Add a chip.
    await combobox.vm.$emit('update:modelValue', ['Berberich_Proband1']);
    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual(['Berberich_Proband1']);

    // Add a second chip.
    await combobox.vm.$emit('update:modelValue', ['Berberich_Proband1', 'Family2_II-1']);
    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual([
      'Berberich_Proband1',
      'Family2_II-1',
    ]);

    // Remove the first chip (closable-chips emits the array without it).
    await combobox.vm.$emit('update:modelValue', ['Family2_II-1']);
    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual(['Family2_II-1']);
  });

  it('defaults subject.alternateIds to [] and hnf1bCuration to {} for a new phenopacket', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual([]);
    expect(wrapper.vm.phenopacket.hnf1bCuration).toEqual({});
  });

  it('defaults hnf1bCuration and subject.alternateIds when loading a legacy record that lacks them', async () => {
    getPhenopacket.mockResolvedValueOnce({
      data: {
        phenopacket: {
          id: 'PP-LEGACY',
          subject: { id: 'SUB-LEGACY', sex: 'UNKNOWN_SEX' },
          phenotypicFeatures: [],
          interpretations: [],
          metaData: { externalReferences: [] },
          // No hnf1bCuration block at all -- this is the legacy shape.
        },
        revision: 1,
        state: 'draft',
      },
    });

    const vuetify = createVuetify({
      components: vuetifyComponents,
      directives: vuetifyDirectives,
    });
    const router = createRouter({
      history: createWebHistory(),
      routes: [
        {
          path: '/phenopackets/:phenopacket_id/edit',
          name: 'EditPhenopacket',
          component: PhenopacketCreateEdit,
        },
      ],
    });
    await router.push('/phenopackets/PP-LEGACY/edit');
    await router.isReady();

    const wrapper = mount(PhenopacketCreateEdit, { global: { plugins: [router, vuetify] } });
    await flushPromises();

    expect(wrapper.vm.phenopacket.hnf1bCuration).toEqual({});
    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual([]);
  });

  it('passes phenopacketForCompleteness (not the raw phenopacket) into CompletenessRail', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    // Reassignment rather than `.push()`: Vue's public-instance proxy for a
    // component mixing `setup()` with Options API `data` does not route an
    // externally-called `wrapper.vm.arr.push()` through the same reactive
    // proxy the render/computed tree tracks (a VTU/Vue quirk unrelated to
    // this component's own code -- `this.publications.push()` called from
    // inside a real method, as `addPublication()` does, is unaffected).
    // Reassigning goes through the tracked `set` trap correctly either way.
    wrapper.vm.publications = [{ pmid: '25324567' }];
    await wrapper.vm.$nextTick();

    const rail = wrapper.findComponent(CompletenessRail);
    expect(rail.exists()).toBe(true);
    expect(rail.props('phenopacket').metaData.externalReferences).toEqual([
      { id: 'PMID:25324567' },
    ]);
    // The raw phenopacket must not have been mutated by reading the computed.
    expect(wrapper.vm.phenopacket.metaData.externalReferences || []).not.toContainEqual({
      id: 'PMID:25324567',
    });
  });
});

// ── Classification section wiring (Task 6) — full mount ────────────────────
// ClassificationSection.vue is exercised in depth by its own suite
// (tests/unit/components/ClassificationSection.spec.js, including the ADR
// 0003 D1 non-negotiable); these prove PhenopacketCreateEdit.vue actually
// mounts it (unlike VariantAnnotationForm, it is NOT stubbed above) and wires
// its vocabulary props to the composable's refs, matching the Case section's
// wiring tests.
describe('Classification section wiring (Task 6)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('wires the Classification system select to phenopacket.hnf1bCuration.classificationSystem using the vocabulary composable', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const select = selectByLabel(wrapper, 'Classification system');
    expect(select).toBeTruthy();
    expect(select.props('items')).toEqual(
      VOCAB_FIXTURES['/ontology/vocabularies/classification-system']
    );

    await select.vm.$emit('update:modelValue', 'acmg');
    expect(wrapper.vm.phenopacket.hnf1bCuration.classificationSystem).toBe('acmg');
  });

  it('passes the interpretation-status vocabulary through to the ACMG verdict select', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const select = selectByLabel(wrapper, 'ACMG verdict');
    expect(select).toBeTruthy();
    expect(select.props('items')).toEqual(
      VOCAB_FIXTURES['/ontology/vocabularies/interpretation-status']
    );
    // No variant on a fresh phenopacket -- disabled until one is added.
    expect(select.props('disabled')).toBe(true);
  });

  it('round-trips Classification date and comment into phenopacket.hnf1bCuration', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const dateField = wrapper
      .findAllComponents({ name: 'VTextField' })
      .find((c) => c.props('label') === 'Classification date');
    const commentField = wrapper
      .findAllComponents({ name: 'VTextarea' })
      .find((c) => c.props('label') === 'Classification comment');
    expect(dateField).toBeTruthy();
    expect(commentField).toBeTruthy();

    await dateField.vm.$emit('update:modelValue', '2024-03-01');
    expect(wrapper.vm.phenopacket.hnf1bCuration.classificationDate).toBe('2024-03-01');

    await commentField.vm.$emit('update:modelValue', 'Reviewed after functional study.');
    expect(wrapper.vm.phenopacket.hnf1bCuration.classificationComment).toBe(
      'Reviewed after functional study.'
    );
  });
});
