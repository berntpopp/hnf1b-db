import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { mount, flushPromises } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import PhenotypicFeaturesSection from '@/components/PhenotypicFeaturesSection.vue';

// `get` must be created via vi.hoisted -- vi.mock factories are hoisted
// above the rest of the module (same requirement as
// usePhenopacketVocabularies.spec.js). useLateralityPolicy.js imports the
// named export `apiClient` from '@/api' and is NOT mocked away (unlike
// useGroupedHPO below) so these tests exercise the real composable against a
// mocked API response -- per Task 7's instruction to "mock the API call,
// don't hit the live DB from a Vitest unit test".
const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/api', () => ({ apiClient: { get } }));

// `groups`/`loading` must be REAL Vue refs, not plain `{value: ...}`
// objects: `<script setup>`'s template-unwrap proxy only unwraps values
// where `isRef()` is true, so a plain object would always be template-truthy
// regardless of `.value`, permanently pinning `v-if="loading"` to true and
// `v-if="!loading"` to false -- hiding the grouped-terms row from every
// DOM-rendering test regardless of what the component does. The original
// three state-transition tests below never rendered the DOM (they call
// `wrapper.vm.cycleState()` directly), so this never surfaced before.
vi.mock('@/composables/useGroupedHPO', () => ({
  useGroupedHPO: () => ({
    groups: ref({
      Kidney: [
        { hpo_id: 'HP:0000107', label: 'Renal cyst' },
        { hpo_id: 'HP:0000122', label: 'Unilateral renal agenesis' },
        { hpo_id: 'HP:0100611', label: 'Multiple glomerular cysts' },
      ],
    }),
    loading: ref(false),
    fetchGrouped: vi.fn(),
  }),
}));

// The laterality/KidneyBiopsy suites below query rendered VSelect component
// instances (findAllComponents({name: ...})) and inspect rendered text,
// which requires Vuetify's components/directives to actually be registered
// on the plugin instance -- matching the distinction VariantAnnotationForm
// .spec.js and PhenopacketCreateEdit.spec.js draw for their own
// DOM-querying suites. Used for every mount in this file (including the
// pre-existing state-transition tests, which only call exposed methods
// directly and never touch the DOM, so the fuller plugin costs them
// nothing).
const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });
const TERM = { hpo_id: 'HP:0000107', label: 'Renal cyst' };

// Real shape confirmed live via psql against hpo_terms_lookup (2026-07-31).
// HP:0000122 admits exactly {Unilateral, Left, Right}, NOT Bilateral.
const LATERALITY_POLICY_ROWS = [
  {
    hpo_id: 'HP:0000107',
    allowed_modifiers: ['HP:0012832', 'HP:0012833', 'HP:0012835', 'HP:0012834'],
  },
  { hpo_id: 'HP:0000122', allowed_modifiers: ['HP:0012833', 'HP:0012835', 'HP:0012834'] },
];

function mountSection(modelValue, extraProps = {}) {
  return mount(PhenotypicFeaturesSection, {
    props: { modelValue, ...extraProps },
    global: { plugins: [fullVuetify] },
  });
}

function findSelectByLabelSubstring(wrapper, substring) {
  return wrapper
    .findAllComponents({ name: 'VSelect' })
    .find((c) => (c.props('label') || '').includes(substring));
}

// File-wide: PhenotypicFeaturesSection now mounts the real
// useLateralityPolicy composable, which logs through window.logService
// (mirrors usePhenopacketVocabularies.js's own convention) -- every test in
// this file would throw on that call without this stub, not just the new
// laterality-specific ones below.
beforeEach(() => {
  get.mockReset();
  get.mockResolvedValue({ data: { data: [] } });
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

describe('PhenotypicFeaturesSection state transitions', () => {
  it('does not mutate the prop array when cycling present -> excluded', () => {
    const original = [{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }];
    const snapshot = structuredClone(original);
    const wrapper = mountSection(original);

    wrapper.vm.cycleState(TERM);

    expect(original).toEqual(snapshot);
  });

  it('emits a new element object rather than the prop element', () => {
    const original = [{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }];
    const wrapper = mountSection(original);

    wrapper.vm.cycleState(TERM);
    const emitted = wrapper.emitted('update:modelValue')[0][0];

    expect(emitted[0]).not.toBe(original[0]);
    expect(emitted[0].excluded).toBe(true);
  });

  it('cycles unknown -> present -> excluded -> unknown', () => {
    let model = [];
    const step = () => {
      const wrapper = mountSection(model);
      wrapper.vm.cycleState(TERM);
      model = wrapper.emitted('update:modelValue')[0][0];
      return model;
    };

    expect(step()).toEqual([{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false }]);
    expect(step()).toEqual([{ type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: true }]);
    expect(step()).toEqual([]);
  });
});

// ── Per-feature laterality (Task 7 §1, design spec §3.4) ────────────────────
// Which term admits which modifiers must ALWAYS come from the live
// GET /ontology/laterality-policy fetch -- never hardcoded/assumed per term.
// These tests mock only the HTTP response, not the composable, so the real
// fetch -> Map -> render pipeline is what's under test.
describe('PhenotypicFeaturesSection laterality (Task 7 §1)', () => {
  beforeEach(() => {
    get.mockImplementation((url) => {
      if (url.includes('/ontology/laterality-policy')) {
        return Promise.resolve({ data: { data: LATERALITY_POLICY_ROWS } });
      }
      return Promise.resolve({ data: { data: [] } });
    });
  });

  it('HP:0000122 offers exactly Unilateral/Left/Right and NOT Bilateral', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: false,
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis');
    expect(select).toBeTruthy();

    const labels = select.props('items').map((i) => i.label);
    expect(labels.sort()).toEqual(['Left', 'Right', 'Unilateral'].sort());
    expect(labels).not.toContain('Bilateral');
  });

  it('a term the policy admits fully offers all 4 modifiers (HP:0000107)', async () => {
    const feature = { type: { id: 'HP:0000107', label: 'Renal cyst' }, excluded: false };
    const wrapper = mountSection([feature]);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Renal cyst');
    expect(select).toBeTruthy();
    expect(
      select
        .props('items')
        .map((i) => i.label)
        .sort()
    ).toEqual(['Bilateral', 'Left', 'Right', 'Unilateral'].sort());
  });

  it('hides the laterality select when the term is unknown (no entry)', async () => {
    const wrapper = mountSection([]);
    await flushPromises();

    expect(findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis')).toBeFalsy();
  });

  it('hides the laterality select when the term is excluded', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: true,
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    expect(findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis')).toBeFalsy();
  });

  it('hides the laterality select for a present term the policy does not admit', async () => {
    const feature = {
      type: { id: 'HP:0100611', label: 'Multiple glomerular cysts' },
      excluded: false,
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    expect(findSelectByLabelSubstring(wrapper, 'Multiple glomerular cysts')).toBeFalsy();
  });

  it('writes the chosen modifier as a single-element modifiers array', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: false,
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis');
    await select.vm.$emit('update:modelValue', 'HP:0012835'); // Left

    const emitted = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(emitted[0].modifiers).toEqual([{ id: 'HP:0012835', label: 'Left' }]);
  });

  it('is mutually exclusive: picking a new modifier replaces rather than appends', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: false,
      modifiers: [{ id: 'HP:0012835', label: 'Left' }],
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis');
    await select.vm.$emit('update:modelValue', 'HP:0012834'); // Right

    const emitted = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(emitted[0].modifiers).toEqual([{ id: 'HP:0012834', label: 'Right' }]);
  });

  it('clearing the select sets modifiers to []', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: false,
      modifiers: [{ id: 'HP:0012835', label: 'Left' }],
    };
    const wrapper = mountSection([feature]);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis');
    await select.vm.$emit('update:modelValue', null);

    const emitted = wrapper.emitted('update:modelValue').at(-1)[0];
    expect(emitted[0].modifiers).toEqual([]);
  });

  it('does not mutate the prop feature when setting a modifier', async () => {
    const feature = {
      type: { id: 'HP:0000122', label: 'Unilateral renal agenesis' },
      excluded: false,
    };
    const original = [feature];
    const snapshot = structuredClone(original);
    const wrapper = mountSection(original);
    await flushPromises();

    const select = findSelectByLabelSubstring(wrapper, 'Unilateral renal agenesis');
    await select.vm.$emit('update:modelValue', 'HP:0012835');

    expect(original).toEqual(snapshot);
  });
});

// ── KidneyBiopsy verification (Task 7 §2) ────────────────────────────────────
// HP:0100611 ("Multiple glomerular cysts") is already present in
// hpo_terms_lookup (group='Kidney', category='KidneyBiopsy',
// recommendation='required' -- verified live via psql 2026-07-31) and
// GET /ontology/hpo/grouped (backend/app/ontology/routers.py:53-100) applies
// no category-based filtering; neither does useGroupedHPO.js or this
// component. These tests prove it already renders and cycles as an ordinary
// tri-state item from a fixture that includes it -- NO frontend fix was
// needed for this bullet of Task 7.
describe('PhenotypicFeaturesSection KidneyBiopsy (Task 7 §2)', () => {
  it('renders HP:0100611 as visible, ordinary content from the grouped-HPO fixture', async () => {
    const wrapper = mountSection([]);
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain('Multiple glomerular cysts');
    expect(text).toContain('HP:0100611');
  });

  it('cycles HP:0100611 through unknown -> present exactly like any other term', () => {
    const term = { hpo_id: 'HP:0100611', label: 'Multiple glomerular cysts' };
    const wrapper = mountSection([]);

    wrapper.vm.cycleState(term);

    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual([
      { type: { id: 'HP:0100611', label: 'Multiple glomerular cysts' }, excluded: false },
    ]);
  });
});

// ── evidence auto-attached from the anchoring publication (Task 7 §3) ───────
describe('PhenotypicFeaturesSection evidence auto-attach (Task 7 §3)', () => {
  const EVIDENCE_CODE_ITEMS = [
    {
      id: 'ECO:0000033',
      label: 'author statement',
      description: 'Evidence from published author statement',
      category: 'literature',
    },
    { id: 'ECO:0000218', label: 'clinical study', description: null, category: 'clinical' },
  ];

  it('attaches evidence from the evidence-code vocabulary and anchoring PMID on unknown -> present', () => {
    const wrapper = mountSection([], {
      evidenceCodeItems: EVIDENCE_CODE_ITEMS,
      anchoringReference: 'PMID:25324567',
    });

    wrapper.vm.cycleState(TERM);

    const emitted = wrapper.emitted('update:modelValue')[0][0];
    expect(emitted[0].evidence).toEqual([
      {
        evidenceCode: { id: 'ECO:0000033', label: 'author statement' },
        reference: { id: 'PMID:25324567' },
      },
    ]);
  });

  it('omits evidence entirely when no publication has been entered yet (anchoringReference is null)', () => {
    const wrapper = mountSection([], {
      evidenceCodeItems: EVIDENCE_CODE_ITEMS,
      anchoringReference: null,
    });

    wrapper.vm.cycleState(TERM);

    const emitted = wrapper.emitted('update:modelValue')[0][0];
    expect(emitted[0]).not.toHaveProperty('evidence');
  });

  it('does not attach evidence when the evidence-code vocabulary has not loaded yet', () => {
    const wrapper = mountSection([], {
      evidenceCodeItems: [],
      anchoringReference: 'PMID:25324567',
    });

    wrapper.vm.cycleState(TERM);

    const emitted = wrapper.emitted('update:modelValue')[0][0];
    expect(emitted[0]).not.toHaveProperty('evidence');
  });

  it('does NOT (re-)attach evidence when toggling an existing present feature to excluded', () => {
    const existingEvidence = [
      {
        evidenceCode: { id: 'ECO:0000218', label: 'clinical study' },
        reference: { id: 'PMID:1' },
      },
    ];
    const existing = [
      {
        type: { id: 'HP:0000107', label: 'Renal cyst' },
        excluded: false,
        evidence: existingEvidence,
      },
    ];
    const wrapper = mountSection(existing, {
      evidenceCodeItems: EVIDENCE_CODE_ITEMS,
      anchoringReference: 'PMID:25324567',
    });

    wrapper.vm.cycleState(TERM);

    const emitted = wrapper.emitted('update:modelValue')[0][0];
    expect(emitted[0].excluded).toBe(true);
    // The pre-existing (different) evidence entry survives untouched --
    // cycling present -> excluded never re-derives evidence.
    expect(emitted[0].evidence).toEqual(existingEvidence);
  });
});
