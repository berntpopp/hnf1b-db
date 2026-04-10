/**
 * HTML sanitization wrapper around DOMPurify.
 *
 * Used before passing any user-authored or markdown-rendered HTML into
 * Vue's v-html directive. Never render untrusted HTML without passing
 * it through this function first.
 *
 * Security hardening via DOMPurify hooks:
 *
 * 1. `uponSanitizeAttribute` removes *any* attribute whose name starts
 *    with `on` (case-insensitive) — covers every event handler the
 *    platform currently defines plus any future ones (onpointerenter,
 *    onanimationstart, etc.). More comprehensive than a fixed allow/deny
 *    list.
 *
 * 2. `afterSanitizeAttributes` adds `rel="noopener noreferrer"` to every
 *    anchor whose `target="_blank"`. This prevents tabnabbing centrally
 *    so individual markdown helpers, templates, or future call sites
 *    don't have to remember the rel attribute.
 *
 * Static config:
 * - ALLOWED_TAGS covers the tag subset emitted by the renderMarkdown /
 *   formatCitation helpers in FAQ.vue and About.vue.
 * - ALLOWED_ATTR is limited to anchor-relevant attributes.
 * - ALLOW_DATA_ATTR is false to prevent data-* abuse.
 */
import DOMPurify from 'dompurify';

const ALLOWED_TAGS = ['strong', 'em', 'b', 'i', 'a', 'p', 'span', 'br', 'ul', 'ol', 'li', 'code'];

const ALLOWED_ATTR = ['href', 'title', 'target', 'rel'];

// Strip any attribute whose name starts with "on" (case-insensitive).
// This is defense-in-depth: even if ALLOWED_ATTR is widened in the
// future, event handlers are structurally blocked.
DOMPurify.addHook('uponSanitizeAttribute', (_node, data) => {
  if (data.attrName && data.attrName.toLowerCase().startsWith('on')) {
    data.keepAttr = false;
  }
});

// Force safe `rel` on any anchor opening in a new tab. Prevents tabnabbing
// regardless of what individual call sites pass in.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.nodeName === 'A' && node.getAttribute('target') === '_blank') {
    node.setAttribute('rel', 'noopener noreferrer');
  }
});

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
    ALLOW_DATA_ATTR: false,
  });
}
