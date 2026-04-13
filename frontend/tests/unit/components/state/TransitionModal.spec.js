import { describe, it, expect, afterEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import TransitionModal from '@/components/state/TransitionModal.vue';

// Strategy: TransitionModal wraps a v-dialog whose content is teleported to
// document.body. The visualViewport polyfill in tests/setup.js ensures the
// overlay watcher doesn't throw. We find the teleported textarea/button via
// document.querySelector on document.body (attached to DOM so teleport works).

let wrapper;

afterEach(() => {
  wrapper?.unmount();
  // Clean up any teleported content left in body
  document.body.innerHTML = '';
});

const mountModal = (props) => {
  const vuetify = createVuetify({ components, directives });
  wrapper = mount(TransitionModal, {
    props,
    global: { plugins: [vuetify] },
    attachTo: document.body,
  });
  return wrapper;
};

describe('TransitionModal', () => {
  it('confirm disabled when reason empty', async () => {
    mountModal({ modelValue: true, toState: 'in_review' });
    await wrapper.vm.$nextTick();
    // canConfirm is false when reason is '' — verify via exposed computed
    expect(wrapper.vm.canConfirm).toBe(false);
    // The confirm button in the teleported dialog should be disabled
    const btn = document.querySelector('[data-testid="confirm-btn"]');
    expect(btn).not.toBeNull();
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('emits confirm with reason', async () => {
    mountModal({ modelValue: true, toState: 'in_review' });
    await wrapper.vm.$nextTick();
    // Find teleported textarea and set value
    const textarea = document.querySelector('textarea');
    expect(textarea).not.toBeNull();
    textarea.value = 'ready for review';
    textarea.dispatchEvent(new Event('input'));
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.canConfirm).toBe(true);
    // Click confirm button
    const btn = document.querySelector('[data-testid="confirm-btn"]');
    btn.click();
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ reason: 'ready for review' }]);
  });

  it('clears reason when dialog closes', async () => {
    mountModal({ modelValue: true, toState: 'in_review' });
    await wrapper.vm.$nextTick();
    const textarea = document.querySelector('textarea');
    textarea.value = 'some reason';
    textarea.dispatchEvent(new Event('input'));
    await wrapper.vm.$nextTick();
    expect(wrapper.vm.canConfirm).toBe(true);
    // Close dialog — watcher resets reason
    await wrapper.setProps({ modelValue: false });
    expect(wrapper.vm.canConfirm).toBe(false);
  });
});
