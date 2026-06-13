/**
 * Unit tests for DistanceStatsCard.vue.
 *
 * Presentational sub-component of ProteinStructure3D. Renders the
 * active-variant distance-to-DNA alert and the pathogenicity/domain
 * legend. No NGL involvement — pure props.
 */
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import DistanceStatsCard from '@/components/gene/protein-structure/DistanceStatsCard.vue';

function mountCard(props = {}) {
  const vuetify = createVuetify({ components, directives });
  return mount(DistanceStatsCard, {
    props: {
      activeVariantDistanceInfo: null,
      colorByDomain: false,
      ...props,
    },
    global: { plugins: [vuetify] },
  });
}

describe('DistanceStatsCard', () => {
  it('always renders the pathogenicity legend', () => {
    const wrapper = mountCard();
    expect(wrapper.text()).toContain('Pathogenicity:');
    expect(wrapper.text()).toContain('Pathogenic');
    expect(wrapper.text()).toContain('VUS');
  });

  it('does not render the distance alert when there is no distance info', () => {
    const wrapper = mountCard({ activeVariantDistanceInfo: null });
    expect(wrapper.text()).not.toContain('Distance to DNA:');
  });

  it('renders the distance alert with the formatted distance and category label', () => {
    const wrapper = mountCard({
      activeVariantDistanceInfo: {
        distanceFormatted: '3.5',
        category: 'close',
        closestDNAAtom: { label: 'DG12.N7' },
      },
    });
    expect(wrapper.text()).toContain('Distance to DNA:');
    expect(wrapper.text()).toContain('3.5');
    expect(wrapper.text()).toContain('Close to DNA - likely functional impact');
    expect(wrapper.text()).toContain('DG12.N7');
  });

  it('hides the domain legend unless colorByDomain is true', () => {
    const hidden = mountCard({ colorByDomain: false });
    expect(hidden.text()).not.toContain('Domains:');

    const shown = mountCard({ colorByDomain: true });
    expect(shown.text()).toContain('Domains:');
    expect(shown.text()).toContain('POU-S (90-173)');
    expect(shown.text()).toContain('POU-H (232-305)');
  });

  it('maps distance category to the correct alert type', () => {
    const vm = mountCard().vm;
    expect(vm.getDistanceAlertType('close')).toBe('error');
    expect(vm.getDistanceAlertType('medium')).toBe('warning');
    expect(vm.getDistanceAlertType('far')).toBe('success');
  });
});
