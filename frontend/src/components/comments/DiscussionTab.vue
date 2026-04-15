<!-- src/components/comments/DiscussionTab.vue -->
<template>
  <div class="discussion-tab">
    <CommentComposer
      :editing-comment="editingComment"
      :submitting="submitting"
      @submit="onSubmit"
      @cancel="editingComment = null"
    />
    <v-divider class="my-4" />
    <CommentList
      :comments="comments"
      :loading="loading"
      :error="error"
      :current-user-id="authStore.user.id"
      :current-user-role="authStore.user.role"
      @edit="onEdit"
      @toggle-resolve="onToggleResolve"
      @delete="onDelete"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useAuthStore } from '@/stores/authStore';
import { useComments } from '@/composables/useComments';
import CommentComposer from './CommentComposer.vue';
import CommentList from './CommentList.vue';

// recordType defaults to 'phenopacket' for the existing PagePhenopacket
// caller, but is exposed as a prop so the component can be reused for
// any record type the backend exposes via /api/v2/comments
// (Copilot PR #254 review, DiscussionTab.vue:47).
const props = defineProps({
  recordId: { type: String, required: true },
  recordType: { type: String, default: 'phenopacket' },
});

const authStore = useAuthStore();
const recordIdRef = ref(props.recordId);
watch(
  () => props.recordId,
  (v) => {
    recordIdRef.value = v;
  }
);

const { comments, loading, error, load, post, edit, resolve, unresolve, remove } = useComments(
  props.recordType,
  recordIdRef
);

const editingComment = ref(null);
const submitting = ref(false);

const onEdit = (c) => {
  editingComment.value = c;
};

const onSubmit = async ({ bodyMarkdown, mentionUserIds }) => {
  submitting.value = true;
  try {
    if (editingComment.value) {
      await edit(editingComment.value.id, bodyMarkdown, mentionUserIds);
      editingComment.value = null;
    } else {
      await post(bodyMarkdown, mentionUserIds);
    }
  } finally {
    submitting.value = false;
  }
};

const onToggleResolve = async (c) => {
  if (c.resolved_at) await unresolve(c.id);
  else await resolve(c.id);
};

const onDelete = async (c) => {
  if (!window.confirm('Delete this comment?')) return;
  await remove(c.id);
};

// Guard: only call load() when recordId is truthy so that mounting the
// component before phenopacketMeta arrives (discussionRecordId === '')
// does not fire a malformed API request.
const safeLoad = () => {
  if (recordIdRef.value) load();
};
onMounted(safeLoad);
watch(() => props.recordId, safeLoad);
</script>

<style scoped>
.discussion-tab {
  padding: 16px;
}
</style>
