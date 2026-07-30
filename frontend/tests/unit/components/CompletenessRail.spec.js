/**
 * Unit tests for CompletenessRail.vue (curation console Task 3).
 *
 * The central semantic under test (curation console design spec §1, §2.1):
 * **absence != `not_reported`**. Absence means "not yet curated" (the curator
 * hasn't touched the field). `not_reported` is an ordinary *selected* value
 * meaning "the source publication is silent" and must count as FILLED for
 * completeness purposes, exactly like any other selected value. The rail must
 * never conflate the two.
 *
 * CURATION_FIELDS ships empty at this point in the programme (Tasks 4/5/6/8
 * append real field entries later). This suite pushes disposable fixture
 * fields into the shared registry for the duration of each test and resets it
 * afterwards so nothing leaks into other suites importing the same module.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import CompletenessRail from '@/components/curation/CompletenessRail.vue';
import { CURATION_FIELDS, CURATION_SECTIONS } from '@/utils/curationFields';

function fixtureField(id, section, path) {
  return {
    id,
    section,
    getValue: (phenopacket) => path.split('.').reduce((acc, key) => acc?.[key], phenopacket),
  };
}

describe('CompletenessRail.vue', () => {
  // CURATION_FIELDS is a real module-level array shared with curationFields.js
  // (Tasks 4-8 push their own entries into it later). Snapshot and restore it
  // around every test so this suite's fixtures never leak into other specs
  // that import the same module in the same worker.
  const originalFields = [...CURATION_FIELDS];

  beforeEach(() => {
    CURATION_FIELDS.length = 0;
  });

  afterEach(() => {
    CURATION_FIELDS.length = 0;
    CURATION_FIELDS.push(...originalFields);
  });

  function mountRail(props = {}) {
    return mount(CompletenessRail, {
      props: {
        phenopacket: {},
        ...props,
      },
    });
  }

  it('counts a field holding the literal string "not_reported" as filled', () => {
    CURATION_FIELDS.push(fixtureField('familyHistory', 'case', 'hnf1bCuration.familyHistory'));

    const wrapper = mountRail({
      phenopacket: { hnf1bCuration: { familyHistory: 'not_reported' } },
    });

    expect(wrapper.text()).toContain('1/1');
  });

  it('counts the same field as NOT filled when it is entirely absent', () => {
    CURATION_FIELDS.push(fixtureField('familyHistory', 'case', 'hnf1bCuration.familyHistory'));

    const wrapper = mountRail({ phenopacket: {} });

    expect(wrapper.text()).toContain('0/1');
  });

  it('never conflates an explicit not_reported value with an absent field', () => {
    CURATION_FIELDS.push(fixtureField('familyHistory', 'case', 'hnf1bCuration.familyHistory'));

    const filledWrapper = mountRail({
      phenopacket: { hnf1bCuration: { familyHistory: 'not_reported' } },
    });
    const absentWrapper = mountRail({ phenopacket: {} });

    // Different filled counts prove the two are never collapsed into one bucket.
    expect(filledWrapper.text()).toContain('1/1');
    expect(absentWrapper.text()).toContain('0/1');
    expect(filledWrapper.text()).not.toBe(absentWrapper.text());
  });

  it('sums filled/total across all registry-backed sections for the overall count', () => {
    CURATION_FIELDS.push(
      fixtureField('a', 'case', 'a'),
      fixtureField('b', 'case', 'b'),
      fixtureField('c', 'variant', 'c')
    );

    const wrapper = mountRail({
      phenopacket: { a: 'yes', c: 'yes' }, // b is absent
      phenotypesCompleteness: { filled: 3, total: 5 },
    });

    // case: 1/2, variant: 1/1, classification: 0/0, phenotypes: 3/5 (verbatim),
    // age: 0/0, provenance: 0/0 -> overall 5/8
    expect(wrapper.text()).toContain('5/8');
  });

  it('uses the phenotypesCompleteness prop verbatim rather than recomputing from the registry', () => {
    // No CURATION_FIELDS entries carry section: 'phenotypes' -- if the rail
    // recomputed from the registry instead of trusting the prop it would show
    // 0/0, not the prop's value.
    const wrapper = mountRail({
      phenopacket: {},
      phenotypesCompleteness: { filled: 7, total: 12 },
    });

    expect(wrapper.text()).toContain('7/12');
  });

  it('renders one row per CURATION_SECTIONS entry', () => {
    const wrapper = mountRail();

    CURATION_SECTIONS.forEach((section) => {
      expect(wrapper.text()).toContain(section.label);
    });
  });

  it('marks a section with a validation error even when otherwise complete', () => {
    CURATION_FIELDS.push(fixtureField('a', 'case', 'a'));

    const wrapper = mountRail({
      phenopacket: { a: 'yes' },
      errors: { case: true },
    });

    // The error glyph must override the "complete" checkmark, and the status
    // must be conveyed as visible/accessible text, not color alone.
    expect(wrapper.text()).toMatch(/error/i);
  });

  it('emits navigate with the section id when a row is activated', async () => {
    const wrapper = mountRail();

    const rows = wrapper.findAll('button.completeness-rail__row');
    expect(rows.length).toBe(CURATION_SECTIONS.length);

    await rows[0].trigger('click');

    expect(wrapper.emitted('navigate')).toBeTruthy();
    expect(wrapper.emitted('navigate')[0]).toEqual([CURATION_SECTIONS[0].id]);
  });
});
