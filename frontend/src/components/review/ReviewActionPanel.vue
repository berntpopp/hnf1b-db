<template>
  <section class="review-actions" aria-labelledby="review-actions-title">
    <h2 id="review-actions-title" class="text-h6 mb-3">Review decisions</h2>

    <v-alert
      v-if="actions.conflict.value"
      data-testid="decision-conflict"
      type="warning"
      variant="tonal"
      role="alert"
    >
      <div class="d-flex ga-2 align-start">
        <v-icon aria-hidden="true">mdi-sync-alert</v-icon>
        <div>
          <strong>Reload required</strong>
          <p class="mb-2">{{ actions.conflict.value.message }}</p>
          <v-btn
            data-testid="reload-review"
            class="decision-action"
            variant="outlined"
            :loading="conflictReloading"
            @click="reloadConflict"
          >
            Reload review
          </v-btn>
        </div>
      </div>
    </v-alert>

    <template v-else>
      <v-alert
        v-if="actions.error.value"
        type="error"
        variant="tonal"
        density="compact"
        class="mb-3"
      >
        {{ actions.error.value.message || 'The review decision could not be saved.' }}
      </v-alert>

      <p v-if="decisionCapabilities.length === 0" class="text-body-2">
        No review decisions are available for this record.
      </p>
      <div v-else class="decision-list">
        <div v-for="capability in decisionCapabilities" :key="capability.action">
          <v-btn
            :data-testid="`action-${capability.action}`"
            class="decision-action"
            block
            :color="actionPresentation(capability.action).color"
            :variant="actionPresentation(capability.action).variant"
            :disabled="isDisabled(capability)"
            @click="openDecision(capability.action, $event)"
          >
            <template #prepend>
              <v-icon aria-hidden="true">{{ actionPresentation(capability.action).icon }}</v-icon>
            </template>
            {{ actionPresentation(capability.action).label }}
          </v-btn>
          <ul v-if="blockerDescriptions(capability).length" class="decision-blockers text-caption">
            <li v-for="description in blockerDescriptions(capability)" :key="description">
              {{ description }}
            </li>
          </ul>
        </div>
      </div>
    </template>

    <ReviewDecisionDialog
      v-model="dialogOpen"
      :action="dialogAction"
      :snapshot="dialogSnapshot"
      :unresolved-count="openIssueCount"
      :submitting="actions.submitting.value"
      @submit="submitDecision"
      @closed="restoreActionFocus"
    />
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue';

import ReviewDecisionDialog from '@/components/review/ReviewDecisionDialog.vue';
import { useReviewActions } from '@/composables/useReviewActions';

const props = defineProps({
  context: { type: Object, required: true },
  reload: { type: Function, required: true },
  onCompleted: { type: Function, default: undefined },
});

const contextRef = computed(() => props.context);
const recordId = computed(() => props.context.phenopacket_id);
const actions = useReviewActions(recordId, contextRef, {
  reload: props.reload,
  onCompleted: props.onCompleted,
});

const dialogOpen = ref(false);
const dialogAction = ref('approve');
const lastActionTrigger = ref(null);
const conflictReloading = ref(false);

const decisionCapabilities = computed(() =>
  (props.context.capabilities || []).filter((capability) =>
    ['request_changes', 'approve', 'publish', 'withdraw'].includes(capability.action)
  )
);
const openIssueCount = computed(
  () => props.context.discussion_summary?.open_blocking_issues ?? null
);
const dialogSnapshot = computed(() => {
  if (dialogAction.value === 'publish' || dialogAction.value === 'reopen_approved') {
    return props.context.approved;
  }
  return props.context.candidate;
});

const ACTIONS = {
  request_changes: {
    label: 'Request changes',
    icon: 'mdi-file-edit-outline',
    color: 'warning',
    variant: 'tonal',
  },
  approve: {
    label: 'Approve candidate',
    icon: 'mdi-check-decagram-outline',
    color: 'success',
    variant: 'tonal',
  },
  publish: {
    label: 'Publish approved revision',
    icon: 'mdi-publish',
    color: 'primary',
    variant: 'flat',
  },
  withdraw: {
    label: 'Withdraw from review',
    icon: 'mdi-undo-variant',
    color: undefined,
    variant: 'outlined',
  },
};

const BLOCKER_COPY = {
  self_review_forbidden: 'You own this draft and cannot independently review it.',
  reviewer_submitted: 'You submitted this candidate and cannot independently review it.',
  reviewer_contributed:
    'You contributed content in this review cycle and cannot independently review it.',
  review_author_unknown: 'Reviewer independence cannot be verified from the audit history.',
  review_closed: 'This review action is no longer available.',
};

function actionPresentation(action) {
  if (action === 'request_changes' && props.context.effective_state === 'approved') {
    return {
      ...ACTIONS.request_changes,
      label: 'Reopen approved review',
      icon: 'mdi-lock-open-variant-outline',
    };
  }
  return ACTIONS[action];
}

function issueCountCopy() {
  if (!Number.isInteger(openIssueCount.value)) {
    return 'Blocking issue status is unavailable. Reload before approving.';
  }
  const label = openIssueCount.value === 1 ? 'issue remains' : 'issues remain';
  return `${openIssueCount.value} unresolved blocking ${label}.`;
}

function blockerDescriptions(capability) {
  const descriptions = (capability.blocked_by || []).map((code) => {
    if (code === 'unresolved_review_issues') return issueCountCopy();
    return BLOCKER_COPY[code] || code.replaceAll('_', ' ');
  });
  if (
    capability.action === 'approve' &&
    (!Number.isInteger(openIssueCount.value) || openIssueCount.value > 0) &&
    !descriptions.includes(issueCountCopy())
  ) {
    descriptions.push(issueCountCopy());
  }
  return descriptions;
}

function isDisabled(capability) {
  if (!capability.allowed) return true;
  if (capability.action !== 'approve') return false;
  return !Number.isInteger(openIssueCount.value) || openIssueCount.value > 0;
}

function openDecision(action, event) {
  lastActionTrigger.value = event.currentTarget;
  dialogAction.value =
    action === 'request_changes' && props.context.effective_state === 'approved'
      ? 'reopen_approved'
      : action;
  dialogOpen.value = true;
}

async function submitDecision(payload) {
  const method = {
    approve: actions.approve,
    request_changes: actions.requestChanges,
    reopen_approved: actions.reopenApproved,
    publish: actions.publish,
    withdraw: actions.withdraw,
  }[dialogAction.value];
  try {
    await method(payload);
    dialogOpen.value = false;
  } catch {
    if (actions.conflict.value) dialogOpen.value = false;
  }
}

async function restoreActionFocus() {
  await nextTick();
  lastActionTrigger.value?.focus();
}

async function reloadConflict() {
  conflictReloading.value = true;
  try {
    await props.reload();
  } finally {
    conflictReloading.value = false;
  }
}
</script>

<style scoped>
.decision-list {
  display: grid;
  gap: 1rem;
}

.decision-action {
  min-height: 44px;
}

.decision-blockers {
  margin: 0.5rem 0 0;
  padding-left: 1.25rem;
}
</style>
