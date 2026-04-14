<template>
  <div>
    <v-alert v-if="error" type="error" density="compact">
      {{ error.message || 'Failed to load comments.' }}
    </v-alert>
    <v-progress-circular v-if="loading && comments.length === 0" indeterminate />
    <CommentItem
      v-for="c in comments"
      :key="c.id"
      :comment="c"
      :current-user-id="currentUserId"
      :current-user-role="currentUserRole"
      @edit="emit('edit', $event)"
      @toggle-resolve="emit('toggleResolve', $event)"
      @delete="emit('delete', $event)"
    />
  </div>
</template>

<script setup>
import CommentItem from './CommentItem.vue';

defineProps({
  comments: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  error: { type: Object, default: null },
  currentUserId: { type: Number, required: true },
  currentUserRole: { type: String, required: true },
});

const emit = defineEmits(['edit', 'toggleResolve', 'delete']);
</script>
