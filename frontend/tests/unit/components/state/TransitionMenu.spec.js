import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

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
    expect(wrapper.find('[data-action="archive"]').attributes('disabled')).toBeDefined();
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
    expect(wrapper.get('[data-action="request_changes"]').attributes('disabled')).toBeDefined();
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
