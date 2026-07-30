import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import PhenotypicFeaturesSection from '@/components/PhenotypicFeaturesSection.vue';

vi.mock('@/composables/useGroupedHPO', () => ({
  useGroupedHPO: () => ({
    groups: { value: { Kidney: [{ hpo_id: 'HP:0000107', label: 'Renal cyst' }] } },
    loading: { value: false },
    fetchGrouped: vi.fn(),
  }),
}));

const vuetify = createVuetify();
const TERM = { hpo_id: 'HP:0000107', label: 'Renal cyst' };

function mountSection(modelValue) {
  return mount(PhenotypicFeaturesSection, {
    props: { modelValue },
    global: { plugins: [vuetify] },
  });
}

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
