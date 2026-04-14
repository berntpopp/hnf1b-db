<template>
  <div class="comment-composer">
    <editor-content :editor="editor" class="composer-editor" />
    <Teleport to="body">
      <div
        v-if="suggestionVisible"
        class="mention-suggestion-wrapper"
        :style="{ top: suggestionPosition.top + 'px', left: suggestionPosition.left + 'px' }"
      >
        <MentionSuggestionList
          ref="suggestionListRef"
          :items="suggestionItems"
          :command="suggestionCommand"
        />
      </div>
    </Teleport>
    <div class="d-flex align-center mt-2">
      <v-btn color="primary" :disabled="!canSubmit" :loading="submitting" @click="onSubmit">
        {{ submitLabel }}
      </v-btn>
      <v-btn v-if="editingComment" variant="text" class="ml-2" @click="$emit('cancel')">
        Cancel
      </v-btn>
      <span class="ml-3 text-caption text-medium-emphasis"> {{ charCount }} / 10000 </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount, watch } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Mention from '@tiptap/extension-mention';
import { Markdown } from 'tiptap-markdown';
import { searchMentionableUsers } from '@/api/domain/comments';
import MentionSuggestionList from './MentionSuggestionList.vue';

const props = defineProps({
  editingComment: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
});

const emit = defineEmits(['submit', 'cancel']);

const content = ref(props.editingComment?.body_markdown ?? '');

// Suggestion popover state
const suggestionVisible = ref(false);
const suggestionItems = ref([]);
const suggestionPosition = ref({ top: 0, left: 0 });
const suggestionCommandRef = ref(null);
const suggestionListRef = ref(null);

const suggestionCommand = (attrs) => {
  if (suggestionCommandRef.value) suggestionCommandRef.value(attrs);
  suggestionVisible.value = false;
};

const mentionExtension = Mention.configure({
  HTMLAttributes: { class: 'mention' },
  renderText: ({ node }) => `@${node.attrs.label ?? node.attrs.id}`,
  suggestion: {
    items: async ({ query }) => {
      if (!query || query.length < 2) return [];
      try {
        const { data } = await searchMentionableUsers(query);
        return data.data.slice(0, 20);
      } catch {
        return [];
      }
    },
    render: () => ({
      onStart: (suggestionProps) => {
        suggestionCommandRef.value = suggestionProps.command;
        suggestionItems.value = suggestionProps.items;
        const rect = suggestionProps.clientRect?.();
        if (rect) {
          suggestionPosition.value = {
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
          };
        }
        suggestionVisible.value = suggestionProps.items.length > 0;
      },
      onUpdate: (suggestionProps) => {
        suggestionItems.value = suggestionProps.items;
        const rect = suggestionProps.clientRect?.();
        if (rect) {
          suggestionPosition.value = {
            top: rect.bottom + window.scrollY,
            left: rect.left + window.scrollX,
          };
        }
        suggestionVisible.value = suggestionProps.items.length > 0;
      },
      onKeyDown: (suggestionProps) =>
        suggestionListRef.value?.onKeyDown?.({ event: suggestionProps.event }) ?? false,
      onExit: () => {
        suggestionVisible.value = false;
        suggestionItems.value = [];
      },
    }),
  },
});

const editor = useEditor({
  content: content.value,
  extensions: [StarterKit, Markdown, mentionExtension],
  onUpdate: ({ editor: ed }) => {
    content.value = ed.storage.markdown.getMarkdown();
  },
});

const charCount = computed(() => content.value.length);

const canSubmit = computed(
  () => !props.submitting && content.value.trim().length >= 1 && content.value.length <= 10000
);

const submitLabel = computed(() => (props.editingComment ? 'Save' : 'Post'));

const collectMentions = () => {
  const ids = [];
  if (!editor.value) return ids;
  editor.value.state.doc.descendants((node) => {
    if (node.type.name === 'mention' && node.attrs.id) {
      ids.push(Number(node.attrs.id));
    }
  });
  return Array.from(new Set(ids));
};

const onSubmit = () => {
  emit('submit', {
    bodyMarkdown: content.value,
    mentionUserIds: collectMentions(),
  });
};

watch(
  () => props.editingComment,
  (c) => {
    if (!editor.value) return;
    if (c) editor.value.commands.setContent(c.body_markdown);
    else editor.value.commands.setContent('');
  }
);

onBeforeUnmount(() => editor.value?.destroy());
</script>

<style scoped>
.composer-editor {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
  padding: 12px;
  min-height: 120px;
}

.composer-editor :deep(.mention) {
  background: rgba(94, 53, 177, 0.1);
  color: rgb(94, 53, 177);
  padding: 2px 4px;
  border-radius: 3px;
}

.composer-editor :deep(.ProseMirror:focus) {
  outline: none;
}

.mention-suggestion-wrapper {
  position: absolute;
  z-index: 2400;
}
</style>
