import { afterEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

import ReviewDecisionDialog from '@/components/review/ReviewDecisionDialog.vue';

let wrapper;

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

function mountDialog(action, overrides = {}) {
  const vuetify = createVuetify({ components, directives });
  wrapper = mount(ReviewDecisionDialog, {
    props: {
      modelValue: true,
      action,
      submitting: false,
      snapshot: { id: 42, content_sha256: `sha256:${'a'.repeat(64)}` },
      unresolvedCount: 0,
      ...overrides,
    },
    attachTo: document.body,
    global: { plugins: [vuetify] },
  });
  return wrapper;
}

function input(selector, value) {
  const element = document.querySelector(selector);
  if (element.type === 'checkbox') element.checked = value;
  else element.value = value;
  element.dispatchEvent(new Event(element.type === 'checkbox' ? 'change' : 'input'));
}

describe('ReviewDecisionDialog', () => {
  it('traps focus and requires rationale plus both affirmative approval attestations', async () => {
    mountDialog('approve');

    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog.getAttribute('aria-labelledby')).toBe('review-decision-dialog-title');
    expect(wrapper.getComponent({ name: 'VDialog' }).props('retainFocus')).toBe(true);
    expect(document.querySelector('[data-testid="decision-submit"]').disabled).toBe(true);
    expect(document.body.textContent).toContain('Candidate revision 42');

    input('#decision-rationale', '  Verified against every candidate change.  ');
    input('#attest-independent-review', true);
    input('#attest-no-conflict', true);
    await wrapper.vm.$nextTick();

    expect(document.querySelector('[data-testid="decision-submit"]').disabled).toBe(false);
    document.querySelector('form').dispatchEvent(new Event('submit'));

    expect(wrapper.emitted('submit')[0]).toEqual([
      {
        rationale: 'Verified against every candidate change.',
        independentReview: true,
        noUnmanagedConflict: true,
      },
    ]);
  });

  it('keeps approval disabled and explains the authoritative unresolved issue count', async () => {
    mountDialog('approve', { unresolvedCount: 2 });
    input('#decision-rationale', 'Review complete.');
    input('#attest-independent-review', true);
    input('#attest-no-conflict', true);
    await wrapper.vm.$nextTick();

    expect(document.body.textContent).toContain('2 unresolved blocking issues remain');
    expect(document.querySelector('[data-testid="decision-submit"]').disabled).toBe(true);
  });

  it('describes exact publication and emits only a trimmed rationale', async () => {
    mountDialog('publish', {
      snapshot: { id: 43, content_sha256: `sha256:${'b'.repeat(64)}` },
    });
    expect(document.body.textContent).toContain('Approved revision 43 will become public');

    input('#decision-rationale', '  Release the independently approved snapshot.  ');
    await wrapper.vm.$nextTick();
    document.querySelector('form').dispatchEvent(new Event('submit'));

    expect(wrapper.emitted('submit')[0]).toEqual([
      { rationale: 'Release the independently approved snapshot.' },
    ]);
  });

  it('accepts at most the backend transition rationale limit', async () => {
    mountDialog('request_changes');
    const textarea = document.querySelector('#decision-rationale');
    const submit = document.querySelector('[data-testid="decision-submit"]');

    expect(textarea.maxLength).toBe(500);
    input('#decision-rationale', 'a'.repeat(500));
    await wrapper.vm.$nextTick();
    expect(submit.disabled).toBe(false);

    input('#decision-rationale', 'a'.repeat(501));
    await wrapper.vm.$nextTick();
    expect(submit.disabled).toBe(true);
  });
});
