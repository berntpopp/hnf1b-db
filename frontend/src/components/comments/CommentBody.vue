<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="comment-body" v-html="safeHtml" />
</template>

<script setup>
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import { sanitize } from '@/utils/sanitize';

const props = defineProps({
  bodyMarkdown: { type: String, required: true },
});

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const safeHtml = computed(() => sanitize(md.render(props.bodyMarkdown ?? '')));
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
</style>
