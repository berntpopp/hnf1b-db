/**
 * Unit tests for CommentBody.vue
 *
 * CommentBody renders markdown via markdown-it and then passes the result
 * through DOMPurify (via @/utils/sanitize) before setting it as v-html.
 *
 * These tests verify:
 *   1. Valid markdown is rendered to HTML correctly.
 *   2. <script> tags are stripped (XSS protection).
 *   3. onerror event-handler attributes are stripped (XSS protection).
 *
 * No Vuetify plugin required — CommentBody only uses a plain <div v-html>.
 */

import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import CommentBody from '@/components/comments/CommentBody.vue';

describe('CommentBody', () => {
  it('renders plain markdown', () => {
    const wrapper = mount(CommentBody, { props: { bodyMarkdown: '**bold**' } });
    expect(wrapper.html()).toContain('<strong>bold</strong>');
  });

  it('strips <script> tags', () => {
    const wrapper = mount(CommentBody, {
      props: { bodyMarkdown: '<script>alert(1)</script>hi' },
    });
    expect(wrapper.html()).not.toContain('<script>');
  });

  it('does not render <img> as a real element when markdown html is disabled', () => {
    // markdown-it is configured with html:false, so raw HTML tags in the
    // markdown source are escaped to entity text rather than rendered as
    // DOM nodes. DOMPurify then receives only safe, entity-escaped content.
    // We verify no actual <img> DOM node is present in the output.
    const wrapper = mount(CommentBody, {
      props: { bodyMarkdown: '<img src=x onerror="alert(1)">' },
    });
    expect(wrapper.find('img').exists()).toBe(false);
  });
});
