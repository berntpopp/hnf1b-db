<template>
  <v-card variant="outlined" class="mb-3">
    <v-card-text>
      <div class="d-flex align-center mb-2">
        <v-avatar size="32" class="mr-3">{{ initials }}</v-avatar>
        <div>
          <strong>@{{ comment.author_username }}</strong>
          <span class="text-caption text-medium-emphasis ml-2">
            {{ formatRelative(comment.created_at) }}
          </span>
          <v-chip v-if="comment.resolved_at" size="x-small" color="success" class="ml-2">
            Resolved
          </v-chip>
        </div>
        <v-spacer />
        <v-menu v-if="canAct">
          <template #activator="{ props: act }">
            <v-btn
              icon="mdi-dots-vertical"
              aria-label="Comment actions"
              variant="text"
              size="small"
              v-bind="act"
            />
          </template>
          <v-list density="compact">
            <v-list-item v-if="isAuthor" @click="emit('edit', comment)">Edit</v-list-item>
            <v-list-item v-if="canToggleResolve" @click="emit('toggleResolve', comment)">
              {{ comment.resolved_at ? 'Unresolve' : 'Resolve' }}
            </v-list-item>
            <v-list-item v-if="canDelete" @click="emit('delete', comment)">Delete</v-list-item>
          </v-list>
        </v-menu>
      </div>

      <CommentBody :body-markdown="comment.body_markdown" />

      <CommentEditHistory v-if="comment.edited" :comment-id="comment.id" class="mt-2" />
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue';
import { formatDistanceToNow } from 'date-fns';
import CommentBody from './CommentBody.vue';
import CommentEditHistory from './CommentEditHistory.vue';

const props = defineProps({
  comment: { type: Object, required: true },
  currentUserId: { type: Number, required: true },
  currentUserRole: { type: String, required: true },
});

const emit = defineEmits(['edit', 'toggleResolve', 'delete']);

const initials = computed(() =>
  (props.comment.author_display_name || props.comment.author_username)
    .split(/\s+/)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
);

const formatRelative = (ts) => formatDistanceToNow(new Date(ts), { addSuffix: true });

const isAuthor = computed(() => props.currentUserId === props.comment.author_id);
const isAdmin = computed(() => props.currentUserRole === 'admin');
const canResolve = computed(
  () => props.currentUserRole === 'curator' || props.currentUserRole === 'admin'
);
const canAct = computed(() => isAuthor.value || isAdmin.value || canResolve.value);
const canToggleResolve = computed(() => canResolve.value);
const canDelete = computed(() => isAuthor.value || isAdmin.value);
</script>
