/**
 * Unit tests for StructureControls.vue.
 *
 * Presentational sub-component of ProteinStructure3D. Renders the
 * representation toggle, DNA/domain switches, reset button, and the
 * optional distance-line button. No NGL involvement — pure props/emits.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import StructureControls from '@/components/gene/protein-structure/StructureControls.vue';

function mountControls(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(StructureControls, {
    props: {
      representation: 'cartoon',
      showDNA: true,
      colorByDomain: false,
      showDistanceLine: false,
      structureLoaded: true,
      hasActiveVariantInStructure: false,
      activeVariantDistanceInfo: null,
      ...props,
    },
    global: { plugins: [vuetify] },
  });
}

describe('StructureControls', () => {
  it('renders the representation toggle with three options', () => {
    const wrapper = mountControls();
    expect(wrapper.text()).toContain('Cartoon');
    expect(wrapper.text()).toContain('Surface');
    expect(wrapper.text()).toContain('Ball+Stick');
  });

  it('emits reset when the Reset View button is clicked', async () => {
    const wrapper = mountControls();
    const resetBtn = wrapper.findAll('button').find((b) => b.text().includes('Reset View'));
    expect(resetBtn).toBeTruthy();
    await resetBtn.trigger('click');
    expect(wrapper.emitted('reset')).toBeTruthy();
  });

  it('hides the distance-line button when no active variant distance info', () => {
    const wrapper = mountControls({
      hasActiveVariantInStructure: false,
      activeVariantDistanceInfo: null,
    });
    expect(wrapper.text()).not.toContain('mdi-ruler');
    // No button should carry the distance label.
    const distBtn = wrapper.findAll('button').find((b) => b.text().includes('Å'));
    expect(distBtn).toBeUndefined();
  });

  it('shows the distance-line button and emits toggle-distance-line on click', async () => {
    const wrapper = mountControls({
      hasActiveVariantInStructure: true,
      activeVariantDistanceInfo: { distanceFormatted: '4.2', category: 'close' },
    });
    const distBtn = wrapper.findAll('button').find((b) => b.text().includes('4.2'));
    expect(distBtn).toBeTruthy();
    await distBtn.trigger('click');
    expect(wrapper.emitted('toggle-distance-line')).toBeTruthy();
  });
});
