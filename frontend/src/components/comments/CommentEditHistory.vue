<template>
  <v-expansion-panels variant="accordion" density="compact">
    <v-expansion-panel @group:selected="load">
      <v-expansion-panel-title>
        <span class="text-caption text-medium-emphasis"> edited &middot; view history </span>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div v-if="loading">Loading&hellip;</div>
        <div v-else-if="edits.length === 0" class="text-caption text-medium-emphasis">
          No edit history.
        </div>
        <div v-else>
          <div v-for="e in edits" :key="e.id" class="mb-3">
            <div class="text-caption text-medium-emphasis mb-1">
              edited by @{{ e.editor_username }} &middot;
              {{ formatRelative(e.edited_at) }}
            </div>
            <CommentBody :body-markdown="e.prev_body" />
          </div>
        </div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup>
import { ref, watch } from 'vue';
import { formatDistanceToNow } from 'date-fns';
import { listCommentEdits } from '@/api/domain/comments';
import CommentBody from './CommentBody.vue';

const props = defineProps({
  commentId: { type: Number, required: true },
});

const edits = ref([]);
const loading = ref(false);
const loaded = ref(false);

const formatRelative = (ts) => formatDistanceToNow(new Date(ts), { addSuffix: true });

const load = async () => {
  if (loaded.value) return;
  loading.value = true;
  try {
    const { data } = await listCommentEdits(props.commentId);
    edits.value = data.data;
    loaded.value = true;
  } finally {
    loading.value = false;
  }
};

watch(
  () => props.commentId,
  () => {
    loaded.value = false;
    edits.value = [];
  }
);
</script>
