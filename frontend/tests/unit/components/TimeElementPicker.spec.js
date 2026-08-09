/**
 * Unit tests for TimeElementPicker.vue (curation console plan Task 8; design
 * spec §3.5). Reusable GA4GH TimeElement editor bound to BOTH
 * `diseases[].onset` and `subject.timeAtLastEncounter` (via AgeSection.vue),
 * covering the three modes the plan requires: congenital, ISO-8601 age, and
 * gestational.
 *
 * Shapes asserted here are the ones verified live against the corpus
 * (psql, 2026-07-31) and documented in the component's own module doc:
 *   congenital:  {ontologyClass: {id: 'HP:0003577', label: 'Congenital onset'}}
 *   age:         {age: {iso8601duration}}   -- the canonical/nested shape;
 *                AgeSection.vue, not this component, flattens it for
 *                timeAtLastEncounter (ADR 0003 D4).
 *   gestational: {gestationalAge: {weeks, days}}
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import TimeElementPicker from '@/components/curation/TimeElementPicker.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

function mountPicker(props = {}) {
  return mount(TimeElementPicker, {
    props: { modelValue: null, label: 'Onset', ...props },
    global: { plugins: [fullVuetify] },
  });
}

function modeToggle(wrapper) {
  return wrapper.findComponent({ name: 'VBtnToggle' });
}

function fieldByLabel(wrapper, label) {
  return wrapper.findAllComponents({ name: 'VTextField' }).find((c) => c.props('label') === label);
}

beforeEach(() => {
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

describe('TimeElementPicker — mode selector', () => {
  it('starts with no mode selected for a null modelValue', () => {
    const wrapper = mountPicker({ modelValue: null });
    expect(modeToggle(wrapper).props('modelValue')).toBeFalsy();
  });

  it('selecting Congenital emits the fixed HP:0003577 OntologyClass', async () => {
    const wrapper = mountPicker();
    await modeToggle(wrapper).vm.$emit('update:model-value', 'congenital');

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{ ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } }],
    ]);
  });

  it('deselecting the active mode emits null (back to "not yet curated")', async () => {
    const wrapper = mountPicker();
    await modeToggle(wrapper).vm.$emit('update:model-value', 'congenital');
    await modeToggle(wrapper).vm.$emit('update:model-value', undefined);

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted[emitted.length - 1]).toEqual([null]);
  });
});

describe('TimeElementPicker — congenital mode reads back correctly', () => {
  it('detects congenital mode from an existing HP:0003577 value', () => {
    const wrapper = mountPicker({
      modelValue: { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } },
    });
    expect(modeToggle(wrapper).props('modelValue')).toBe('congenital');
  });
});

describe('TimeElementPicker — age (ISO-8601) mode', () => {
  it('typing years/months/days assembles an ISO-8601 duration under the nested {age:} shape', async () => {
    const wrapper = mountPicker();
    await modeToggle(wrapper).vm.$emit('update:model-value', 'age');

    const years = fieldByLabel(wrapper, 'Onset — years');
    const months = fieldByLabel(wrapper, 'Onset — months');
    expect(years).toBeTruthy();
    expect(months).toBeTruthy();

    await years.vm.$emit('update:model-value', '5');
    await months.vm.$emit('update:model-value', '3');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted[emitted.length - 1]).toEqual([{ age: { iso8601duration: 'P5Y3M' } }]);
  });

  it('a years-only entry omits the M/D units, matching the corpus style ("P16Y", not "P16Y0M0D")', async () => {
    const wrapper = mountPicker();
    await modeToggle(wrapper).vm.$emit('update:model-value', 'age');
    const years = fieldByLabel(wrapper, 'Onset — years');
    await years.vm.$emit('update:model-value', '16');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted[emitted.length - 1]).toEqual([{ age: { iso8601duration: 'P16Y' } }]);
  });

  it('reads back an existing nested {age: {iso8601duration}} value (the onset/diseases[] convention)', () => {
    const wrapper = mountPicker({ modelValue: { age: { iso8601duration: 'P20Y9M' } } });
    expect(modeToggle(wrapper).props('modelValue')).toBe('age');
    expect(fieldByLabel(wrapper, 'Onset — years').props('modelValue')).toBe(20);
    expect(fieldByLabel(wrapper, 'Onset — months').props('modelValue')).toBe(9);
  });

  it('reads back an existing flat {iso8601duration} value (the timeAtLastEncounter convention)', () => {
    const wrapper = mountPicker({ modelValue: { iso8601duration: 'P6Y6M' } });
    expect(modeToggle(wrapper).props('modelValue')).toBe('age');
    expect(fieldByLabel(wrapper, 'Onset — years').props('modelValue')).toBe(6);
    expect(fieldByLabel(wrapper, 'Onset — months').props('modelValue')).toBe(6);
  });

  it('clearing all Y/M/D fields back out emits null', async () => {
    const wrapper = mountPicker({ modelValue: { age: { iso8601duration: 'P5Y' } } });
    const years = fieldByLabel(wrapper, 'Onset — years');
    await years.vm.$emit('update:model-value', '');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted[emitted.length - 1]).toEqual([null]);
  });
});

describe('TimeElementPicker — gestational mode', () => {
  it('typing weeks/days emits the standard GA4GH TimeElement.gestationalAge shape', async () => {
    const wrapper = mountPicker();
    await modeToggle(wrapper).vm.$emit('update:model-value', 'gestational');

    const weeks = fieldByLabel(wrapper, 'Onset — gestational weeks');
    const days = fieldByLabel(wrapper, 'Onset — gestational days');
    expect(weeks).toBeTruthy();
    expect(days).toBeTruthy();

    await weeks.vm.$emit('update:model-value', '32');
    await days.vm.$emit('update:model-value', '3');

    const emitted = wrapper.emitted('update:modelValue');
    expect(emitted[emitted.length - 1]).toEqual([{ gestationalAge: { weeks: 32, days: 3 } }]);
  });

  it('reads back an existing gestationalAge value', () => {
    const wrapper = mountPicker({ modelValue: { gestationalAge: { weeks: 30, days: 1 } } });
    expect(modeToggle(wrapper).props('modelValue')).toBe('gestational');
    expect(fieldByLabel(wrapper, 'Onset — gestational weeks').props('modelValue')).toBe(30);
    expect(fieldByLabel(wrapper, 'Onset — gestational days').props('modelValue')).toBe(1);
  });
});

describe('TimeElementPicker — reusability across labels', () => {
  it('applies the label prop to its field labels so two instances (Onset / Age reported) are distinguishable', async () => {
    const wrapper = mountPicker({ label: 'Age reported' });
    await modeToggle(wrapper).vm.$emit('update:model-value', 'age');
    expect(fieldByLabel(wrapper, 'Age reported — years')).toBeTruthy();
  });
});
