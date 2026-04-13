import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import EditingBanner from '@/components/state/EditingBanner.vue';

const mountBanner = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(EditingBanner, { props, global: { plugins: [vuetify] } });
};

describe('EditingBanner', () => {
  it('shows owner CTA when current user owns the draft', () => {
    const wrapper = mountBanner({
      editingRevisionId: 42,
      draftOwnerUsername: 'alice',
      currentUsername: 'alice',
      startedAt: '2026-04-12T10:00:00Z',
    });
    expect(wrapper.text()).toContain('Continue editing');
  });

  it('shows read-only variant for non-owner', () => {
    const wrapper = mountBanner({
      editingRevisionId: 42,
      draftOwnerUsername: 'alice',
      currentUsername: 'bob',
      startedAt: '2026-04-12T10:00:00Z',
    });
    expect(wrapper.text()).toContain('@alice');
    expect(wrapper.text()).not.toContain('Continue editing');
  });

  it('renders nothing when no active edit', () => {
    const wrapper = mountBanner({ editingRevisionId: null });
    expect(wrapper.find('.v-alert').exists()).toBe(false);
  });
});
