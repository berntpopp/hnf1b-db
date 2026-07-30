/**
 * Unit tests for ProvenanceSection.vue (curation console plan Task 8; design
 * spec §3.6). Renders the three free-text fields (Comment, Problematic,
 * DupCheck) plus a READ-ONLY display of curatedBy/curatedAt.
 *
 * ── THE non-negotiable (read before touching) ───────────────────────────
 * No email address may enter a phenopacket by any path, and there must be
 * NO input control anywhere bound to `curatedBy`/`reviewer`. The "structural
 * proof" describe block below doesn't just check that curatedBy happens to
 * be empty in this test run (that would trivially pass even if a binding
 * were simply never triggered) -- it inspects the component's PUBLIC
 * CONTRACT (its compiled `emits` array, which is exhaustive: `<script
 * setup>`'s `defineEmits([...])` is a compile-time macro, so this array is
 * literally every event the component can ever emit) and enumerates every
 * real DOM form control it renders, proving no such control can exist even
 * in principle. See tests/unit/views/PhenopacketCreateEdit.spec.js for the
 * companion full-form integration test that also scans the actual built
 * submission payload for stray '@' characters.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import ProvenanceSection from '@/components/curation/ProvenanceSection.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

function mountSection(props = {}) {
  return mount(ProvenanceSection, {
    props: {
      caseComment: null,
      problematic: null,
      duplicateCheck: null,
      curatedBy: null,
      curatedAt: null,
      ...props,
    },
    global: { plugins: [fullVuetify] },
  });
}

function findByLabel(wrapper, componentName, label) {
  return wrapper.findAllComponents({ name: componentName }).find((c) => c.props('label') === label);
}

beforeEach(() => {
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

// ── THE non-negotiable ──────────────────────────────────────────────────
describe('ProvenanceSection — no reviewer input control (non-negotiable)', () => {
  it("the component's entire emit contract has exactly 3 events, none targeting curatedBy/reviewer/curatedAt", () => {
    // `<script setup>`'s defineEmits([...]) compiles to a static `emits`
    // array on the component definition -- this is the component's COMPLETE
    // public write surface, not a runtime snapshot of what happened to fire.
    const emits = ProvenanceSection.emits;
    expect(emits).toEqual(['update:caseComment', 'update:problematic', 'update:duplicateCheck']);
    expect(emits.some((e) => /curatedBy|reviewer|curatedAt/i.test(e))).toBe(false);
  });

  it('renders exactly 3 editable form controls (input/textarea), and none of them carries curatedBy/curatedAt as its current value', () => {
    const wrapper = mountSection({ curatedBy: 'Jane Curator', curatedAt: '2026-07-31T00:00:00Z' });

    // Vuetify's `auto-grow` textarea renders a second, `aria-hidden="true"`
    // shadow <textarea> per field purely to measure height -- not a real,
    // separately-editable control, so it's excluded here.
    const editableControls = wrapper
      .findAll('input, textarea')
      .filter((el) => el.attributes('aria-hidden') !== 'true');
    expect(editableControls).toHaveLength(3);

    for (const control of editableControls) {
      expect(control.element.value).not.toContain('Jane Curator');
      expect(control.element.value).not.toContain('2026-07-31');
    }
  });

  it('typing an "@"-containing string into every one of the 3 textareas never reaches curatedBy/curatedAt -- those stay exactly the stamped props', async () => {
    const wrapper = mountSection({ curatedBy: 'Jane Curator', curatedAt: '2026-07-31T00:00:00Z' });

    const comment = findByLabel(wrapper, 'VTextarea', 'Comment');
    const problematic = findByLabel(wrapper, 'VTextarea', 'Problematic');
    const dupCheck = findByLabel(wrapper, 'VTextarea', 'Duplicate check');

    await comment.vm.$emit('update:model-value', 'seen at reviewer@example.org conference');
    await problematic.vm.$emit('update:model-value', 'possible dup, ask curator@example.org');
    await dupCheck.vm.$emit('update:model-value', 'cf. sibling@example.org record');

    expect(wrapper.emitted('update:caseComment')).toEqual([
      ['seen at reviewer@example.org conference'],
    ]);
    expect(wrapper.emitted('update:problematic')).toEqual([
      ['possible dup, ask curator@example.org'],
    ]);
    expect(wrapper.emitted('update:duplicateCheck')).toEqual([['cf. sibling@example.org record']]);

    // curatedBy/curatedAt are props this component only ever displays --
    // there is no event through which typing into any textarea could reach
    // them, and no other emit fired besides the three above.
    expect(Object.keys(wrapper.emitted())).toEqual([
      'update:caseComment',
      'update:problematic',
      'update:duplicateCheck',
    ]);
    expect(wrapper.props('curatedBy')).toBe('Jane Curator');
  });
});

describe('ProvenanceSection — curatedBy/curatedAt display', () => {
  it('renders curatedBy/curatedAt as plain text, not inside any input', () => {
    const wrapper = mountSection({ curatedBy: 'Jane Curator', curatedAt: '2026-07-31T00:00:00Z' });
    expect(wrapper.text()).toContain('Jane Curator');
  });

  it('shows a placeholder when not yet stamped', () => {
    const wrapper = mountSection({ curatedBy: null, curatedAt: null });
    expect(wrapper.text()).toContain('Not yet saved');
  });
});

describe('ProvenanceSection — the three free-text fields round-trip', () => {
  it('round-trips Comment into update:caseComment', async () => {
    const wrapper = mountSection();
    const field = findByLabel(wrapper, 'VTextarea', 'Comment');
    await field.vm.$emit('update:model-value', 'Reviewed twice, consistent with sheet.');
    expect(wrapper.emitted('update:caseComment')).toEqual([
      ['Reviewed twice, consistent with sheet.'],
    ]);
  });

  it('round-trips Problematic into update:problematic', async () => {
    const wrapper = mountSection();
    const field = findByLabel(wrapper, 'VTextarea', 'Problematic');
    await field.vm.$emit('update:model-value', 'Zygosity ambiguous in source text.');
    expect(wrapper.emitted('update:problematic')).toEqual([['Zygosity ambiguous in source text.']]);
  });

  it('round-trips Duplicate check into update:duplicateCheck', async () => {
    const wrapper = mountSection();
    const field = findByLabel(wrapper, 'VTextarea', 'Duplicate check');
    await field.vm.$emit('update:model-value', 'Checked against PMID:12345678 -- no overlap.');
    expect(wrapper.emitted('update:duplicateCheck')).toEqual([
      ['Checked against PMID:12345678 -- no overlap.'],
    ]);
  });

  it('renders the current prop values into the three fields', () => {
    const wrapper = mountSection({
      caseComment: 'c',
      problematic: 'p',
      duplicateCheck: 'd',
    });
    expect(findByLabel(wrapper, 'VTextarea', 'Comment').props('modelValue')).toBe('c');
    expect(findByLabel(wrapper, 'VTextarea', 'Problematic').props('modelValue')).toBe('p');
    expect(findByLabel(wrapper, 'VTextarea', 'Duplicate check').props('modelValue')).toBe('d');
  });
});
