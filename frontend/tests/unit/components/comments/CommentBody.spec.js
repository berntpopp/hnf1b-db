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

  it('strips <img onerror> even when markdown html:true is enabled', () => {
    // markdown-it is configured with html:true so that Tiptap mention spans
    // survive rendering. DOMPurify still strips dangerous tags/attributes
    // (img is not in ALLOWED_TAGS), so no actual <img> DOM node is present.
    const wrapper = mount(CommentBody, {
      props: { bodyMarkdown: '<img src=x onerror="alert(1)">' },
    });
    expect(wrapper.find('img').exists()).toBe(false);
  });

  it('preserves <span class="mention"> through sanitization', () => {
    // Mention pills serialized by Tiptap use <span class="mention" data-id="42">
    // and must survive DOMPurify (ALLOWED_TAGS includes span; class and data-id
    // are in ALLOWED_ATTR).
    const wrapper = mount(CommentBody, {
      props: {
        bodyMarkdown: 'hi <span class="mention" data-id="42">@alice</span>',
      },
    });
    expect(wrapper.find('.mention').exists()).toBe(true);
    expect(wrapper.find('.mention').attributes('data-id')).toBe('42');
  });
});
