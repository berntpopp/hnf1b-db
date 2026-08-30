<template>
  <section class="review-issues" aria-labelledby="review-issues-title">
    <div class="review-issues__heading">
      <h2 id="review-issues-title" class="text-h6">Blocking issues</h2>
      <v-btn
        data-testid="create-issue"
        color="primary"
        size="small"
        :disabled="!createIssueCapability.allowed"
        @click="openDialog('create')"
      >
        Create issue
      </v-btn>
    </div>
    <p v-if="!createIssueCapability.allowed && createBlockers" class="text-caption">
      Create issue unavailable: {{ createBlockers }}.
    </p>

    <v-alert v-if="error" type="error" density="compact" class="my-3">
      {{ error.message || 'The blocking issue could not be updated.' }}
    </v-alert>
    <p v-if="orderedIssues.length === 0" class="text-body-2 mt-3">No blocking issues.</p>
    <ol v-else class="review-issues__list">
      <li
        v-for="issue in orderedIssues"
        :key="issue.id"
        data-testid="review-issue"
        class="review-issue"
      >
        <div class="review-issue__heading">
          <strong>{{ issue.author_display_name || issue.author_username }}</strong>
          <span class="issue-status">{{ issue.resolved_at ? 'Resolved' : 'Open' }}</span>
        </div>
        <CommentBody :body-markdown="issue.body_markdown" />

        <ul v-if="issue.resolution_events.length" class="resolution-events">
          <li v-for="event in issue.resolution_events" :key="event.id">
            {{ event.action === 'resolved' ? 'Resolved' : 'Reopened' }} by
            {{ event.actor_username }}: {{ sanitized(event.rationale) }}
          </li>
        </ul>

        <div v-for="capability in issue.capabilities" :key="capability.action" class="mt-2">
          <v-btn
            v-if="capability.action === 'resolve' || capability.action === 'reopen'"
            size="small"
            variant="outlined"
            :disabled="!capability.allowed"
            @click="openDialog(capability.action, issue)"
          >
            {{ capability.action === 'resolve' ? 'Resolve issue' : 'Reopen issue' }}
          </v-btn>
          <span v-if="!capability.allowed && blockerText(capability)" class="text-caption ml-2">
            {{ blockerText(capability) }}
          </span>
        </div>
      </li>
    </ol>

    <span role="status" aria-live="polite" class="sr-only">{{ liveMessage }}</span>

    <ReviewIssueDialog
      v-model="dialogOpen"
      :mode="dialogMode"
      :submitting="submitting"
      @submit="submitDialog"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';

import CommentBody from '@/components/comments/CommentBody.vue';
import ReviewIssueDialog from '@/components/review/ReviewIssueDialog.vue';
import { useReviewIssues } from '@/composables/useReviewIssues';
import { sanitize } from '@/utils/sanitize';

const props = defineProps({
  issues: { type: Array, default: () => [] },
  recordId: { type: String, required: true },
  recordRevision: { type: Number, required: true },
  candidateRevisionId: { type: Number, required: true },
  createIssueCapability: {
    type: Object,
    default: () => ({ action: 'create_issue', allowed: false, blocked_by: [] }),
  },
  reload: { type: Function, required: true },
  liveMessage: { type: String, default: '' },
});

const { submitting, error, createIssue, resolveIssue, reopenIssue } = useReviewIssues({
  recordId: computed(() => props.recordId),
  recordRevision: computed(() => props.recordRevision),
  candidateRevisionId: computed(() => props.candidateRevisionId),
  reload: props.reload,
});

const dialogOpen = ref(false);
const dialogMode = ref('create');
const selectedIssue = ref(null);

const orderedIssues = computed(() =>
  [...props.issues].sort((left, right) => Number(!!left.resolved_at) - Number(!!right.resolved_at))
);

const blockerText = (capability) =>
  (capability.blocked_by || []).map((blocker) => blocker.replaceAll('_', ' ')).join(', ');
const createBlockers = computed(() => blockerText(props.createIssueCapability));
const sanitized = (value) => sanitize(value || '');

function openDialog(mode, issue = null) {
  dialogMode.value = mode;
  selectedIssue.value = issue;
  dialogOpen.value = true;
}

async function submitDialog(payload) {
  if (dialogMode.value === 'create') await createIssue(payload);
  else if (dialogMode.value === 'resolve') await resolveIssue(selectedIssue.value, payload);
  else await reopenIssue(selectedIssue.value, payload);
  dialogOpen.value = false;
}
</script>

<style scoped>
.review-issues__heading,
.review-issue__heading {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.review-issues__list {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.review-issue {
  border: 1px solid rgb(var(--v-theme-surface-variant));
  border-radius: 4px;
  margin-bottom: 0.75rem;
  padding: 0.75rem;
}

.issue-status {
  font-weight: 600;
}

.resolution-events {
  margin-top: 0.75rem;
}

.sr-only {
  clip: rect(0, 0, 0, 0);
  clip-path: inset(50%);
  height: 1px;
  overflow: hidden;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}
</style>
