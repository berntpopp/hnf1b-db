/**
 * HTML sanitization wrapper around DOMPurify.
 *
 * Used before passing any user-authored or markdown-rendered HTML into
 * Vue's v-html directive. Never render untrusted HTML without passing
 * it through this function first.
 *
 * Config notes:
 * - ALLOWED_TAGS covers the tags produced by renderMarkdown() helpers in
 *   FAQ.vue and About.vue (strong, em, a, p, span, br, ul, ol, li).
 * - ALLOWED_ATTR is limited to href, title, target, rel on anchors.
 * - ALLOW_DATA_ATTR is false to prevent data-* event binding abuse.
 * - FORBID_ATTR explicitly blocks event handler attributes even if a
 *   future config change widens ALLOWED_ATTR.
 */
import DOMPurify from 'dompurify';

const ALLOWED_TAGS = ['strong', 'em', 'b', 'i', 'a', 'p', 'span', 'br', 'ul', 'ol', 'li', 'code'];

const ALLOWED_ATTR = ['href', 'title', 'target', 'rel'];

const FORBID_ATTR = [
  'onerror',
  'onload',
  'onclick',
  'onmouseover',
  'onfocus',
  'onblur',
  'onsubmit',
  'onchange',
];

/**
 * Sanitize an HTML string for safe use with v-html.
 *
 * @param {string | null | undefined} html - Raw HTML string.
 * @returns {string} Sanitized HTML, or empty string for null/undefined.
 */
export function sanitize(html) {
  if (html == null || html === '') {
    return '';
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    FORBID_ATTR,
    ALLOW_DATA_ATTR: false,
  });
}
