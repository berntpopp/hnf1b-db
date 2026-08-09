/**
 * Unit tests for AgeSection.vue (curation console plan Task 8; design spec
 * §3.5). Wires two TimeElementPicker instances to `diseases[0].onset` and
 * `subject.timeAtLastEncounter`, and is the ONE place that adapts
 * TimeElementPicker's canonical nested output to `timeAtLastEncounter`'s
 * flat convention (ADR 0003 D4) -- TimeElementPicker itself stays ignorant
 * of which field it's bound to.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';
import AgeSection from '@/components/curation/AgeSection.vue';
import TimeElementPicker from '@/components/curation/TimeElementPicker.vue';

const fullVuetify = createVuetify({ components: vuetifyComponents, directives: vuetifyDirectives });

function mountSection(props = {}) {
  return mount(AgeSection, {
    props: { diseases: [], timeAtLastEncounter: null, ...props },
    global: { plugins: [fullVuetify] },
  });
}

function pickers(wrapper) {
  return wrapper.findAllComponents(TimeElementPicker);
}

beforeEach(() => {
  window.logService = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
});

describe('AgeSection — onset (diseases[0].onset)', () => {
  it('mounts two TimeElementPicker instances (onset, age reported)', () => {
    const wrapper = mountSection();
    expect(pickers(wrapper)).toHaveLength(2);
  });

  it('when diseases is empty, picking an onset creates a placeholder disease entry defaulting to the corpus disease term', async () => {
    const wrapper = mountSection({ diseases: [] });
    const onsetPicker = pickers(wrapper)[0];

    await onsetPicker.vm.$emit('update:modelValue', {
      ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' },
    });

    const emitted = wrapper.emitted('update:diseases');
    expect(emitted).toBeTruthy();
    expect(emitted[0][0]).toEqual([
      {
        term: { id: 'MONDO:0007669', label: 'renal cysts and diabetes syndrome' },
        onset: { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } },
      },
    ]);
  });

  it('when a disease entry already exists, onset is set on it without disturbing its term or other fields', async () => {
    const wrapper = mountSection({
      diseases: [
        {
          term: { id: 'MONDO:0007669', label: 'renal cysts and diabetes syndrome' },
          diseaseStage: [{ id: 'HP:0012622', label: 'Chronic kidney disease' }],
        },
      ],
    });
    const onsetPicker = pickers(wrapper)[0];

    await onsetPicker.vm.$emit('update:modelValue', { age: { iso8601duration: 'P5Y' } });

    const emitted = wrapper.emitted('update:diseases');
    const diseases = emitted[emitted.length - 1][0];
    expect(diseases).toHaveLength(1);
    expect(diseases[0].term).toEqual({
      id: 'MONDO:0007669',
      label: 'renal cysts and diabetes syndrome',
    });
    expect(diseases[0].diseaseStage).toEqual([
      { id: 'HP:0012622', label: 'Chronic kidney disease' },
    ]);
    expect(diseases[0].onset).toEqual({ age: { iso8601duration: 'P5Y' } });
  });

  it('passes diseases[0].onset (not the whole diseases array) as the onset picker modelValue', () => {
    const onset = { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } };
    const wrapper = mountSection({ diseases: [{ term: { id: 'MONDO:0007669' }, onset }] });
    expect(pickers(wrapper)[0].props('modelValue')).toEqual(onset);
  });

  it('onset writes are passed through unchanged -- no flattening (matches the corpus nested {age:} convention)', async () => {
    const wrapper = mountSection({ diseases: [] });
    const onsetPicker = pickers(wrapper)[0];

    await onsetPicker.vm.$emit('update:modelValue', { age: { iso8601duration: 'P41Y' } });

    const emitted = wrapper.emitted('update:diseases');
    expect(emitted[0][0][0].onset).toEqual({ age: { iso8601duration: 'P41Y' } });
  });
});

describe('AgeSection — age reported (subject.timeAtLastEncounter, ADR 0003 D4)', () => {
  it('passes timeAtLastEncounter straight through as the second picker modelValue', () => {
    const t = { iso8601duration: 'P41Y' };
    const wrapper = mountSection({ timeAtLastEncounter: t });
    expect(pickers(wrapper)[1].props('modelValue')).toEqual(t);
  });

  it("flattens the picker's nested {age: {iso8601duration}} write into the corpus's flat {iso8601duration} shape", async () => {
    const wrapper = mountSection();
    const ageReportedPicker = pickers(wrapper)[1];

    await ageReportedPicker.vm.$emit('update:modelValue', { age: { iso8601duration: 'P41Y' } });

    expect(wrapper.emitted('update:timeAtLastEncounter')).toEqual([[{ iso8601duration: 'P41Y' }]]);
  });

  it('does NOT flatten a congenital (ontologyClass) write -- the corpus already stores that flat/top-level for this field too', async () => {
    const wrapper = mountSection();
    const ageReportedPicker = pickers(wrapper)[1];

    const congenital = { ontologyClass: { id: 'HP:0003577', label: 'Congenital onset' } };
    await ageReportedPicker.vm.$emit('update:modelValue', congenital);

    expect(wrapper.emitted('update:timeAtLastEncounter')).toEqual([[congenital]]);
  });

  it('does NOT flatten a gestational write', async () => {
    const wrapper = mountSection();
    const ageReportedPicker = pickers(wrapper)[1];

    const gestational = { gestationalAge: { weeks: 32, days: 3 } };
    await ageReportedPicker.vm.$emit('update:modelValue', gestational);

    expect(wrapper.emitted('update:timeAtLastEncounter')).toEqual([[gestational]]);
  });

  it('passes a null (cleared) write straight through', async () => {
    const wrapper = mountSection({ timeAtLastEncounter: { iso8601duration: 'P41Y' } });
    const ageReportedPicker = pickers(wrapper)[1];

    await ageReportedPicker.vm.$emit('update:modelValue', null);

    expect(wrapper.emitted('update:timeAtLastEncounter')).toEqual([[null]]);
  });
});
