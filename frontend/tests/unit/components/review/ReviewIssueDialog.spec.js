import { afterEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';

import ReviewIssueDialog from '@/components/review/ReviewIssueDialog.vue';

let wrapper;

afterEach(() => {
  wrapper?.unmount();
  document.body.innerHTML = '';
});

function mountDialog(mode) {
  const vuetify = createVuetify({ components, directives });
  wrapper = mount(ReviewIssueDialog, {
    props: { modelValue: true, mode, submitting: false },
    attachTo: document.body,
    global: { plugins: [vuetify] },
  });
  return wrapper;
}

describe('ReviewIssueDialog', () => {
  it('offers only the backend disposition allowlist and requires rationale to resolve', async () => {
    mountDialog('resolve');
    expect(document.querySelector('[role="dialog"]').getAttribute('aria-labelledby')).toBe(
      'review-issue-dialog-title'
    );
    const options = Array.from(document.querySelectorAll('option')).map((option) => option.value);

    expect(options).toEqual([
      '',
      'addressed',
      'accepted_with_rationale',
      'retracted',
      'superseded',
    ]);
    expect(document.querySelector('[data-testid="issue-submit"]').disabled).toBe(true);

    const select = document.querySelector('select');
    select.value = 'addressed';
    select.dispatchEvent(new Event('change'));
    const textarea = document.querySelector('textarea');
    textarea.value = 'Verified against the candidate snapshot.';
    textarea.dispatchEvent(new Event('input'));
    await wrapper.vm.$nextTick();
    document.querySelector('form').dispatchEvent(new Event('submit'));

    expect(wrapper.emitted('submit')[0]).toEqual([
      { disposition: 'addressed', rationale: 'Verified against the candidate snapshot.' },
    ]);
  });

  it('requires rationale when reopening an issue', async () => {
    mountDialog('reopen');
    expect(document.querySelector('[data-testid="issue-submit"]').disabled).toBe(true);

    const textarea = document.querySelector('textarea');
    textarea.value = 'Candidate edit regressed the correction.';
    textarea.dispatchEvent(new Event('input'));
    await wrapper.vm.$nextTick();
    document.querySelector('form').dispatchEvent(new Event('submit'));

    expect(wrapper.emitted('submit')[0]).toEqual([
      { rationale: 'Candidate edit regressed the correction.' },
    ]);
  });

  it('creates an issue from a non-empty body', async () => {
    mountDialog('create');
    const textarea = document.querySelector('textarea');
    textarea.value = 'Please correct the inheritance evidence.';
    textarea.dispatchEvent(new Event('input'));
    await wrapper.vm.$nextTick();
    document.querySelector('form').dispatchEvent(new Event('submit'));

    expect(wrapper.emitted('submit')[0]).toEqual([
      { bodyMarkdown: 'Please correct the inheritance evidence.' },
    ]);
  });
});
