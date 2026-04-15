<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="comment-body" v-html="safeHtml" />
</template>

<script setup>
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

const props = defineProps({
  bodyMarkdown: { type: String, required: true },
});

// html: true lets the Tiptap-serialized mention span survive into the
// rendered tree. DOMPurify below strips anything dangerous.
const md = new MarkdownIt({ html: true, linkify: true, breaks: true });

// Comment-specific sanitize config. We allow `class` and a narrow set of
// data-* attributes so <span class="mention" data-id="..."> survives and
// renders as a styled pill. Everything else follows DOMPurify defaults.
const sanitizeForComment = (html) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'strong',
      'em',
      'b',
      'i',
      'a',
      'p',
      'span',
      'br',
      'ul',
      'ol',
      'li',
      'code',
      'pre',
      'blockquote',
    ],
    // 'target' is intentionally omitted: markdown links do not need it and
    // allowing it would let user content set target="_blank" without rel,
    // enabling tabnabbing (Copilot review #254 comment #8).
    ALLOWED_ATTR: ['href', 'title', 'rel', 'class', 'data-id', 'data-type'],
    // Event handlers are still blocked — ALLOWED_ATTR doesn't include any on* names.
  });

const safeHtml = computed(() => sanitizeForComment(md.render(props.bodyMarkdown ?? '')));
</script>

<style scoped>
.comment-body :deep(p) {
  margin-bottom: 0.5em;
}
.comment-body :deep(code) {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.9em;
}
.comment-body :deep(.mention) {
  background: rgba(94, 53, 177, 0.1);
  color: rgb(94, 53, 177);
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: 500;
}
</style>
