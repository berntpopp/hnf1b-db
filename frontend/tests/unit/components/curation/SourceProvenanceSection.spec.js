import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import SourceProvenanceSection from '@/components/curation/reports/SourceProvenanceSection.vue';

const observed = (raw, value) => ({ raw, sourceStatus: 'stated', value, correctionIds: [] });
const observation = (id, onset) => ({
  observationId: id,
  source: {},
  sourceReview: {},
  case: {},
  ages: { onset: observed('source age', onset) },
  notes: {},
});

describe('SourceProvenanceSection temporal editing', () => {
  it('does not invent age zero and emits a valid duration only after entry', async () => {
    const wrapper = mount(SourceProvenanceSection, {
      props: { modelValue: observation('one', { kind: 'unprojected' }) },
    });
    await wrapper.get('[name="age-onset-kind"]').setValue('gestationalAge');
    expect(wrapper.emitted('update:modelValue')).toBeUndefined();
    await wrapper.get('[name="age-onset"]').setValue('P28W');
    expect(wrapper.emitted('update:modelValue').at(-1)[0].ages.onset.value).toEqual({
      kind: 'gestationalAge',
      iso8601Duration: 'P28W',
    });
  });

  it('keeps pending modes scoped to the selected observation', async () => {
    const wrapper = mount(SourceProvenanceSection, {
      props: { modelValue: observation('one', { kind: 'unprojected' }) },
    });
    await wrapper.get('[name="age-onset-kind"]').setValue('gestationalAge');
    await wrapper.setProps({
      modelValue: observation('two', { kind: 'age', iso8601Duration: 'P12Y' }),
    });
    expect(wrapper.get('[name="age-onset-kind"]').element.value).toBe('age');
  });
});
