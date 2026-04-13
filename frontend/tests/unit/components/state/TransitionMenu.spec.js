import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import TransitionMenu from '@/components/state/TransitionMenu.vue';

// Note: v-menu in Vuetify triggers the overlay positioning logic on click which
// requires `visualViewport` — unavailable in happy-dom. We therefore test the
// role-gating logic via the component's exposed `items` computed (populated via
// defineExpose) without opening the actual overlay. The activator button and
// transition-item slots are separately confirmed to exist in the DOM.

const mountMenu = (props) => {
  const vuetify = createVuetify({ components, directives });
  return mount(TransitionMenu, { props, global: { plugins: [vuetify] } });
};

describe('TransitionMenu', () => {
  it('curator owner on draft sees submit only', () => {
    const wrapper = mountMenu({
      currentState: 'draft',
      role: 'curator',
      isOwner: true,
    });
    const labels = wrapper.vm.items.map((i) => i.label);
    expect(labels).toContain('Submit for review');
    expect(labels).not.toContain('Approve');
    expect(labels).not.toContain('Request changes');
  });

  it('viewer sees nothing', () => {
    const wrapper = mountMenu({
      currentState: 'draft',
      role: 'viewer',
      isOwner: true,
    });
    expect(wrapper.vm.items).toHaveLength(0);
  });

  it('admin on in_review sees approve and request_changes', () => {
    const wrapper = mountMenu({
      currentState: 'in_review',
      role: 'admin',
      isOwner: false,
    });
    const labels = wrapper.vm.items.map((i) => i.label);
    expect(labels).toContain('Approve');
    expect(labels).toContain('Request changes');
  });

  it('admin on draft sees in_review and archived', () => {
    const wrapper = mountMenu({
      currentState: 'draft',
      role: 'admin',
      isOwner: false,
    });
    const tos = wrapper.vm.items.map((i) => i.to);
    expect(tos).toContain('in_review');
    expect(tos).toContain('archived');
  });

  it('admin on changes_requested sees in_review and archived', () => {
    const wrapper = mountMenu({
      currentState: 'changes_requested',
      role: 'admin',
      isOwner: false,
    });
    const tos = wrapper.vm.items.map((i) => i.to);
    expect(tos).toContain('in_review');
    expect(tos).toContain('archived');
  });

  it('curator owner on draft sees submit only (no archive)', () => {
    const wrapper = mountMenu({
      currentState: 'draft',
      role: 'curator',
      isOwner: true,
    });
    const tos = wrapper.vm.items.map((i) => i.to);
    expect(tos).toEqual(['in_review']);
  });

  it('menu activator button is rendered', () => {
    const wrapper = mountMenu({
      currentState: 'draft',
      role: 'curator',
      isOwner: true,
    });
    expect(wrapper.find('[data-testid="menu-activator"]').exists()).toBe(true);
  });
});
