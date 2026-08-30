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
    props: ['modelValue', 'formSubmitted', 'evidenceCodeItems', 'anchoringReference'],
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
vi.mock('@/components/curation/reports/ReportObservationWorkspace.vue', () => ({
  default: {
    name: 'ReportObservationWorkspace',
    props: ['phenopacketId', 'recordState'],
    template: '<div class="mock-report-observation-workspace" />',
  },
}));

// Task 8: PhenopacketCreateEdit.vue's setup() now calls useAuthStore() to
// source curatedBy's display name (the no-reviewer-input-control
// non-negotiable -- see ProvenanceSection.vue's module doc). Mocked the same
// way tests/unit/views/PagePhenopacket.spec.js already does (a plain object
// returned from the mocked composable, not a real Pinia instance -- this
// view's tests never install a Pinia plugin).
vi.mock('@/stores/authStore', () => ({ useAuthStore: vi.fn() }));

import { getPhenopacket, updatePhenopacket } from '@/api';
import { useAuthStore } from '@/stores/authStore';
import PhenopacketCreateEdit from '@/views/PhenopacketCreateEdit.vue';
import CompletenessRail from '@/components/curation/CompletenessRail.vue';
import ProvenanceSection from '@/components/curation/ProvenanceSection.vue';

/** Curation console Task 8: the session identity stampCuration() reads. */
function mockAuthenticatedCurator(userOverrides = {}) {
  useAuthStore.mockReturnValue({
    user: {
      username: 'jane.curator',
      full_name: 'Jane Curator',
      role: 'curator',
      ...userOverrides,
    },
  });
}

/**
 * Recursively walks a JSON-serializable value and returns the dotted path of
 * every string leaf containing '@'. Used by the Task 8 no-email non-
 * negotiable test to prove '@' reaches the submission payload ONLY through
 * the three free-text fields a curator explicitly controls, never through
 * curatedBy/reviewer/createdBy or any other path.
 */
function findAtSignPaths(value, path = '') {
  if (typeof value === 'string') {
    return value.includes('@') ? [path] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((v, i) => findAtSignPaths(v, `${path}[${i}]`));
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([k, v]) => findAtSignPaths(v, path ? `${path}.${k}` : k));
  }
  return [];
}

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
    stampCuration: PhenopacketCreateEdit.methods.stampCuration,
    curatorDisplayName: PhenopacketCreateEdit.methods.curatorDisplayName,
    // Task 8: stampCuration()/curatorDisplayName read this. Direct-method-call
    // tests (via createContext()) never go through the real setup(), so a
    // default stub is needed here for handleSubmit/buildSubmissionPhenopacket
    // to not throw on `this.authStore.user`.
    authStore: { user: { username: 'jane.curator', full_name: 'Jane Curator' } },
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

  it('uses the editing revision effective state instead of the published head state', async () => {
    getPhenopacket.mockResolvedValueOnce({
      data: { ...phenopacketResponse, state: 'published', effective_state: 'approved' },
    });
    const ctx = createContext();

    await PhenopacketCreateEdit.methods.loadPhenopacket.call(ctx);

    expect(ctx.savedRecordState).toBe('approved');
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
  '/ontology/vocabularies/evidence-code': [
    {
      id: 'ECO:0000033',
      label: 'author statement',
      description: 'Evidence from published author statement',
      category: 'literature',
    },
    { id: 'ECO:0000218', label: 'clinical study', description: null, category: 'clinical' },
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
    mockAuthenticatedCurator();
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

  it('defaults subject.alternateIds to [] and hnf1bCuration to {} (before Task 8 stamping) for a new phenopacket', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    expect(wrapper.vm.phenopacket.subject.alternateIds).toEqual([]);
    // Task 8 (design spec §3.6): hnf1bCuration starts at {} (unchanged from
    // Task 4) but is no longer EMPTY by the time mounted() finishes --
    // stampCuration() immediately stamps curatedBy/curatedAt, with no other
    // key leaking in (see "curatorDisplayName / stampCuration (Task 8)"
    // below for the dedicated stampCuration suite).
    expect(wrapper.vm.phenopacket.hnf1bCuration).toEqual({
      curatedBy: 'Jane Curator',
      curatedAt: expect.any(String),
    });
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

    // Task 8: hnf1bCuration is defaulted to {} and then immediately stamped
    // (curatedBy/curatedAt) by mounted() -- see the sibling "new phenopacket"
    // test above for the same note.
    expect(wrapper.vm.phenopacket.hnf1bCuration).toEqual({
      curatedBy: 'Jane Curator',
      curatedAt: expect.any(String),
    });
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
    mockAuthenticatedCurator();
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

// ── Phenotypes section wiring (Task 7) — full mount ─────────────────────────
// PhenotypicFeaturesSection itself is stubbed above (see the vi.mock block
// at the top of this file) and is exercised in depth by its own suite
// (tests/unit/components/PhenotypicFeaturesSection.spec.js); these prove
// PhenopacketCreateEdit.vue actually passes it the two new props the design
// spec §3.4 evidence-attachment behaviour needs: the evidence-code
// vocabulary (never hardcoded -- sourced from usePhenopacketVocabularies)
// and the anchoring publication reference (the first listed publication's
// PMID, formatted `PMID:...`, or null until one has been entered).
describe('Phenotypes section wiring (Task 7)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    mockAuthenticatedCurator();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('passes the evidence-code vocabulary into PhenotypicFeaturesSection', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const section = wrapper.findComponent({ name: 'PhenotypicFeaturesSection' });
    expect(section.exists()).toBe(true);
    expect(section.props('evidenceCodeItems')).toEqual(
      VOCAB_FIXTURES['/ontology/vocabularies/evidence-code']
    );
  });

  it('passes anchoringReference as null when no publication has been entered', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const section = wrapper.findComponent({ name: 'PhenotypicFeaturesSection' });
    expect(section.props('anchoringReference')).toBeNull();
  });

  it('passes anchoringReference as PMID:<first pmid> once one is entered, ignoring later ones', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    wrapper.vm.publications = [{ pmid: '25324567' }, { pmid: '99999999' }];
    await wrapper.vm.$nextTick();

    const section = wrapper.findComponent({ name: 'PhenotypicFeaturesSection' });
    expect(section.props('anchoringReference')).toBe('PMID:25324567');
  });

  it('treats a publication row with a blank PMID as no publication entered yet', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    wrapper.vm.publications = [{ pmid: '' }];
    await wrapper.vm.$nextTick();

    const section = wrapper.findComponent({ name: 'PhenotypicFeaturesSection' });
    expect(section.props('anchoringReference')).toBeNull();
  });
});

// ── phenotypesCompleteness (Task 7) ──────────────────────────────────────
// Formula: filled = total = phenopacket.phenotypicFeatures.length. By
// construction (PhenotypicFeaturesSection's own tri-state convention -- see
// that component's `cycleState`/`getState`) an entry only exists once a
// curator has made an explicit present/excluded choice, so every entry is
// "unambiguously curated" and the section is always N/N once anything has
// been entered. There is no fixed universe size to divide by here, unlike
// the fixed-schema sections' CURATION_FIELDS registry.
describe('phenotypesCompleteness (Task 7)', () => {
  const computeIt = PhenopacketCreateEdit.computed.phenotypesCompleteness;

  it('is 0/0 with no phenotypic features', () => {
    const ctx = { phenopacket: { phenotypicFeatures: [] } };
    expect(computeIt.call(ctx)).toEqual({ filled: 0, total: 0 });
  });

  it('is N/N for N curated features, counting both present and excluded entries', () => {
    const ctx = {
      phenopacket: {
        phenotypicFeatures: [
          { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false },
          { type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' }, excluded: true },
          { type: { id: 'HP:0100611', label: 'Multiple glomerular cysts' }, excluded: false },
        ],
      },
    };
    expect(computeIt.call(ctx)).toEqual({ filled: 3, total: 3 });
  });

  it('tolerates a missing phenotypicFeatures array', () => {
    const ctx = { phenopacket: {} };
    expect(computeIt.call(ctx)).toEqual({ filled: 0, total: 0 });
  });
});

// ── curatorDisplayName / stampCuration (Task 8) ─────────────────────────────
// curatedBy/curatedAt (+ metaData.reviewer) are stamped from the
// authenticated session's display name and the client clock -- NEVER from a
// form field. See ProvenanceSection.spec.js and the "no email" suite below
// for the structural absence-of-a-control proof; these cover the stamping
// logic itself.
describe('curatorDisplayName / stampCuration (Task 8)', () => {
  const displayName = PhenopacketCreateEdit.methods.curatorDisplayName;
  const stamp = PhenopacketCreateEdit.methods.stampCuration;

  it('curatorDisplayName prefers full_name over username', () => {
    const ctx = { authStore: { user: { full_name: 'Jane Curator', username: 'jane.c' } } };
    expect(displayName.call(ctx)).toBe('Jane Curator');
  });

  it('curatorDisplayName falls back to username when full_name is absent', () => {
    const ctx = { authStore: { user: { username: 'jane.c' } } };
    expect(displayName.call(ctx)).toBe('jane.c');
  });

  it('curatorDisplayName falls back to an empty string when there is no user', () => {
    expect(displayName.call({ authStore: { user: null } })).toBe('');
    expect(displayName.call({ authStore: {} })).toBe('');
  });

  it('stampCuration sets hnf1bCuration.curatedBy/curatedAt and metaData.reviewer from the session and the client clock', () => {
    const ctx = createContext({
      authStore: { user: { full_name: 'Jane Curator', username: 'jane.c' } },
      phenopacket: {
        id: 'PP-001',
        subject: { id: 'SUB-001' },
        hnf1bCuration: {},
        metaData: {},
      },
    });
    // stampCuration is a real method on the ctx object (see createContext),
    // referencing `this.curatorDisplayName()` -- attach it too.
    ctx.curatorDisplayName = displayName;

    const before = Date.now();
    stamp.call(ctx);
    const after = Date.now();

    expect(ctx.phenopacket.hnf1bCuration.curatedBy).toBe('Jane Curator');
    expect(ctx.phenopacket.metaData.reviewer).toBe('Jane Curator');
    const stampedTime = new Date(ctx.phenopacket.hnf1bCuration.curatedAt).getTime();
    expect(stampedTime).toBeGreaterThanOrEqual(before);
    expect(stampedTime).toBeLessThanOrEqual(after);
  });

  it('stampCuration defensively creates hnf1bCuration/metaData when a legacy record lacks either', () => {
    const ctx = createContext({
      authStore: { user: { username: 'jane.c' } },
      phenopacket: { id: 'PP-LEGACY', subject: { id: 'SUB-LEGACY' } },
    });
    ctx.curatorDisplayName = displayName;

    stamp.call(ctx);

    expect(ctx.phenopacket.hnf1bCuration.curatedBy).toBe('jane.c');
    expect(ctx.phenopacket.metaData.reviewer).toBe('jane.c');
  });

  it('handleSubmit re-stamps curatedAt with a fresher timestamp at actual submit time', async () => {
    updatePhenopacket.mockResolvedValueOnce({ data: { phenopacket_id: 'PP-001' } });
    const ctx = createContext({
      authStore: { user: { full_name: 'Jane Curator' } },
      isEditing: true,
      phenopacket: {
        id: 'PP-001',
        subject: { id: 'SUB-001', sex: 'UNKNOWN_SEX' },
        phenotypicFeatures: [{ id: 'HP:0000001' }],
        interpretations: [],
        hnf1bCuration: { curatedBy: 'Jane Curator', curatedAt: '2020-01-01T00:00:00.000Z' },
        metaData: { externalReferences: [], reviewer: 'Jane Curator' },
      },
      changeReason: 'Fixed a typo',
      revision: 7,
    });
    ctx.curatorDisplayName = displayName;

    await PhenopacketCreateEdit.methods.handleSubmit.call(ctx);

    const submitted = updatePhenopacket.mock.calls[0][1].phenopacket;
    expect(submitted.hnf1bCuration.curatedBy).toBe('Jane Curator');
    expect(new Date(submitted.hnf1bCuration.curatedAt).getTime()).toBeGreaterThan(
      new Date('2020-01-01T00:00:00.000Z').getTime()
    );
  });

  it('mounted() stamps curatedBy/curatedAt/reviewer immediately -- the Provenance badge reads filled right away', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    expect(wrapper.vm.phenopacket.hnf1bCuration.curatedBy).toBe('Jane Curator');
    expect(wrapper.vm.phenopacket.hnf1bCuration.curatedAt).toBeTruthy();
    expect(wrapper.vm.phenopacket.metaData.reviewer).toBe('Jane Curator');
  });
});

// ── Age section wiring (Task 8) — full mount ────────────────────────────────
describe('Age section wiring (Task 8)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    mockAuthenticatedCurator();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('mounts AgeSection wired to phenopacket.diseases and subject.timeAtLastEncounter', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const ageSection = wrapper.findComponent({ name: 'AgeSection' });
    expect(ageSection.exists()).toBe(true);
    expect(ageSection.props('diseases')).toEqual([]);
    expect(ageSection.props('timeAtLastEncounter')).toBeNull();
  });

  it('update:diseases from AgeSection writes phenopacket.diseases (AgeOnset)', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const ageSection = wrapper.findComponent({ name: 'AgeSection' });
    const diseases = [
      {
        term: { id: 'MONDO:0007669', label: 'renal cysts and diabetes syndrome' },
        onset: { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } },
      },
    ];
    await ageSection.vm.$emit('update:diseases', diseases);

    expect(wrapper.vm.phenopacket.diseases).toEqual(diseases);
  });

  it('update:timeAtLastEncounter from AgeSection writes subject.timeAtLastEncounter (AgeReported)', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const ageSection = wrapper.findComponent({ name: 'AgeSection' });
    await ageSection.vm.$emit('update:timeAtLastEncounter', { iso8601duration: 'P41Y' });

    expect(wrapper.vm.phenopacket.subject.timeAtLastEncounter).toEqual({
      iso8601duration: 'P41Y',
    });
  });
});

// ── Provenance section wiring (Task 8) — full mount ─────────────────────────
describe('Provenance section wiring (Task 8)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    mockAuthenticatedCurator();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('mounts ProvenanceSection wired to the five hnf1bCuration provenance fields', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const provenance = wrapper.findComponent({ name: 'ProvenanceSection' });
    expect(provenance.exists()).toBe(true);
    expect(provenance.props('curatedBy')).toBe('Jane Curator');
    expect(provenance.props('curatedAt')).toBeTruthy();
    expect(provenance.props('caseComment')).toBeNull();
  });

  it('update:caseComment / update:problematic / update:duplicateCheck write into phenopacket.hnf1bCuration', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const provenance = wrapper.findComponent({ name: 'ProvenanceSection' });
    await provenance.vm.$emit('update:caseComment', 'note');
    await provenance.vm.$emit('update:problematic', 'issue');
    await provenance.vm.$emit('update:duplicateCheck', 'checked');

    expect(wrapper.vm.phenopacket.hnf1bCuration.caseComment).toBe('note');
    expect(wrapper.vm.phenopacket.hnf1bCuration.problematic).toBe('issue');
    expect(wrapper.vm.phenopacket.hnf1bCuration.duplicateCheck).toBe('checked');
  });
});

// ── No email / no reviewer-input-control (Task 8 non-negotiable) ───────────
// One of the programme's three global non-negotiable tests. Proves, at the
// full-form level, that '@' can only ever reach the built submission
// payload through the three free-text fields a curator explicitly controls
// (caseComment/problematic/duplicateCheck) -- never through
// hnf1bCuration.curatedBy, metaData.reviewer, metaData.createdBy, or any
// other path. Combined with ProvenanceSection.spec.js's component-level
// structural proof (its compiled `emits` array has no curatedBy/reviewer
// event at all), this proves absence of a control, not merely that one
// happened to stay empty in this run.
describe('No email / no reviewer-input-control (Task 8 non-negotiable)', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockVocabularyApi();
    mockAuthenticatedCurator();
    window.logService = {
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    };
  });

  it('typing "@" into every Task 8 textarea reaches the submission payload ONLY at the three free-text paths', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    // Also feed a PMID and phenotype so the payload resembles a real save,
    // and set a subject id -- none of these are expected to contain '@'.
    wrapper.vm.publications = [{ pmid: '25324567' }];
    wrapper.vm.phenopacket.subject.id = 'SUB-001';
    await wrapper.vm.$nextTick();

    const provenance = wrapper.findComponent({ name: 'ProvenanceSection' });
    await provenance.vm.$emit('update:caseComment', 'seen at reviewer@example.org conference');
    await provenance.vm.$emit('update:problematic', 'possible dup, ask curator@example.org');
    await provenance.vm.$emit('update:duplicateCheck', 'cf. sibling@example.org record');

    const submitted = wrapper.vm.buildSubmissionPhenopacket();
    const atSignPaths = findAtSignPaths(submitted);

    expect(atSignPaths.sort()).toEqual(
      [
        'hnf1bCuration.caseComment',
        'hnf1bCuration.problematic',
        'hnf1bCuration.duplicateCheck',
      ].sort()
    );
  });

  it('curatedBy and metaData.reviewer are always exactly the authenticated display name, never derived from a free-text field', async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const provenance = wrapper.findComponent({ name: 'ProvenanceSection' });
    await provenance.vm.$emit('update:caseComment', 'Dr. Evil <evil@example.org> reviewed this');

    const submitted = wrapper.vm.buildSubmissionPhenopacket();
    expect(submitted.hnf1bCuration.curatedBy).toBe('Jane Curator');
    expect(submitted.metaData.reviewer).toBe('Jane Curator');
    expect(submitted.hnf1bCuration.curatedBy).not.toContain('@');
    expect(submitted.metaData.reviewer).not.toContain('@');
  });

  it("ProvenanceSection's entire public emit contract is mounted as-is -- no wrapper/override adds a curatedBy/reviewer event", async () => {
    const wrapper = await mountCreateForm();
    await flushPromises();

    const provenance = wrapper.findComponent({ name: 'ProvenanceSection' });
    expect(provenance.exists()).toBe(true);
    expect(ProvenanceSection.emits).toEqual([
      'update:caseComment',
      'update:problematic',
      'update:duplicateCheck',
    ]);
  });
});
