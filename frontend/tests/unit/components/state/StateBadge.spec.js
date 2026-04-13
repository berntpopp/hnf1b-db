import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import StateBadge from '@/components/state/StateBadge.vue';

const mountWithVuetify = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(StateBadge, { props, global: { plugins: [vuetify] } });
};

describe('StateBadge', () => {
  it.each([
    ['draft', 'grey'],
    ['in_review', 'blue'],
    ['changes_requested', 'orange'],
    ['approved', 'purple'],
    ['published', 'green'],
    ['archived', 'brown'],
  ])('renders %s with color %s', (state, color) => {
    const wrapper = mountWithVuetify({ state });
    expect(wrapper.text().toLowerCase()).toContain(state.replace('_', ' '));
    expect(
      wrapper
        .find('.v-chip')
        .classes()
        .some((c) => c.includes(color))
    ).toBe(true);
  });

  it('renders null state as empty', () => {
    const wrapper = mountWithVuetify({ state: null });
    expect(wrapper.find('.v-chip').exists()).toBe(false);
  });
});
