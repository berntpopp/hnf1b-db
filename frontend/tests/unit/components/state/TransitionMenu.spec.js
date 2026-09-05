import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { createVuetify } from 'vuetify';
import * as vuetifyComponents from 'vuetify/components';
import * as vuetifyDirectives from 'vuetify/directives';

import TransitionMenu from '@/components/state/TransitionMenu.vue';

const VMenuStub = {
  template:
    '<div><slot name="activator" :props="{}" /><div data-testid="menu-content"><slot /></div></div>',
};
const VListStub = { template: '<div><slot /></div>' };
const VListItemStub = {
  inheritAttrs: false,
  props: { disabled: Boolean },
  emits: ['click'],
  template:
    '<button v-bind="$attrs" type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
};
const TextStub = { template: '<span><slot /></span>' };
const VBtnStub = {
  inheritAttrs: false,
  template: '<button v-bind="$attrs" type="button"><slot /></button>',
};
const fullVuetify = createVuetify({
  components: vuetifyComponents,
  directives: vuetifyDirectives,
});

const mountMenu = (capabilities) =>
  mount(TransitionMenu, {
    props: { capabilities },
    global: {
      stubs: {
        VMenu: VMenuStub,
        VList: VListStub,
        VListItem: VListItemStub,
        VListItemTitle: TextStub,
        VListItemSubtitle: TextStub,
        VBtn: VBtnStub,
      },
    },
  });

const mountRealListItemMenu = (capabilities) =>
  mount(TransitionMenu, {
    props: { capabilities },
    global: {
      plugins: [fullVuetify],
      stubs: { VMenu: VMenuStub },
    },
  });

describe('TransitionMenu', () => {
  it('renders only server-returned state actions and their denial reasons', () => {
    const wrapper = mountMenu([
      { action: 'submit', allowed: true, blocked_by: [] },
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
      { action: 'create_issue', allowed: true, blocked_by: [] },
    ]);

    expect(wrapper.text()).toContain('Submit for review');
    expect(wrapper.text()).toContain('Archive');
    expect(wrapper.text()).toContain('Only an administrator can perform this action.');
    expect(wrapper.text()).not.toContain('Create issue');
    expect(wrapper.findAll('[data-testid="transition-item"]')).toHaveLength(2);
    expect(wrapper.find('[data-action="archive"]').attributes('aria-disabled')).toBe('true');
  });

  it('keeps blocked reasons focusable and denies pointer and keyboard activation', async () => {
    const wrapper = mountMenu([
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ]);
    const blocked = wrapper.get('[data-action="archive"]');

    expect(blocked.attributes('aria-disabled')).toBe('true');
    expect(blocked.attributes('tabindex')).toBe('0');
    expect(blocked.text()).toContain('Only an administrator can perform this action.');

    await blocked.trigger('click');
    await blocked.trigger('keydown', { key: 'Enter' });
    await blocked.trigger('keydown', { key: ' ' });

    expect(wrapper.emitted('transition')).toBeUndefined();
    expect(wrapper.emitted('open-review')).toBeUndefined();
  });

  it.each([
    ['mouse click', 'submit', 'click', undefined, 'transition', 'in_review'],
    ['Enter', 'submit', 'keydown', 'Enter', 'transition', 'in_review'],
    ['Space', 'approve', 'keydown', ' ', 'open-review', 'approve'],
  ])(
    'real Vuetify emits an allowed action exactly once for %s',
    async (_label, action, eventName, key, emittedEvent, payload) => {
      const wrapper = mountRealListItemMenu([{ action, allowed: true, blocked_by: [] }]);
      const item = wrapper.get(`[data-action="${action}"]`);

      await item.trigger(eventName, key ? { key } : undefined);

      expect(wrapper.emitted(emittedEvent)).toEqual([[payload]]);
      wrapper.unmount();
    }
  );

  it.each(['Enter', ' '])('real Vuetify denies blocked keyboard activation for %s', async (key) => {
    const wrapper = mountRealListItemMenu([
      { action: 'archive', allowed: false, blocked_by: ['forbidden_role'] },
    ]);
    const blocked = wrapper.get('[data-action="archive"]');

    await blocked.trigger('keydown', { key });

    expect(blocked.attributes('aria-disabled')).toBe('true');
    expect(blocked.attributes('tabindex')).toBe('0');
    expect(blocked.text()).toContain('Only an administrator can perform this action.');
    expect(wrapper.emitted('transition')).toBeUndefined();
    expect(wrapper.emitted('open-review')).toBeUndefined();
    wrapper.unmount();
  });

  it('emits only payload-compatible transitions from allowed capabilities', async () => {
    const wrapper = mountMenu([
      { action: 'resubmit', allowed: true, blocked_by: [] },
      { action: 'withdraw', allowed: true, blocked_by: [] },
      { action: 'archive', allowed: true, blocked_by: [] },
    ]);

    await wrapper.get('[data-action="resubmit"]').trigger('click');
    await wrapper.get('[data-action="withdraw"]').trigger('click');
    await wrapper.get('[data-action="archive"]').trigger('click');

    expect(wrapper.emitted('transition')).toEqual([['in_review'], ['draft'], ['archived']]);
  });

  it('routes exact decision actions to the focused workspace', async () => {
    const wrapper = mountMenu([
      { action: 'request_changes', allowed: false, blocked_by: ['reviewer_contributed'] },
      { action: 'approve', allowed: true, blocked_by: [] },
      { action: 'publish', allowed: true, blocked_by: [] },
    ]);

    expect(wrapper.text()).toContain('You contributed to this review cycle.');
    expect(wrapper.get('[data-action="request_changes"]').attributes('aria-disabled')).toBe('true');
    await wrapper.get('[data-action="approve"]').trigger('click');
    await wrapper.get('[data-action="publish"]').trigger('click');

    expect(wrapper.emitted('open-review')).toEqual([['approve'], ['publish']]);
    expect(wrapper.emitted('transition')).toBeUndefined();
  });

  it('has no local state, role, or ownership policy props', () => {
    const wrapper = mountMenu([]);

    expect(Object.keys(wrapper.vm.$options.props)).toEqual(['capabilities']);
    expect(wrapper.find('[data-testid="menu-activator"]').exists()).toBe(false);
  });
});
