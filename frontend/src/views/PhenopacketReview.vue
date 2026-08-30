<template>
  <v-container fluid class="review-page py-6">
    <section
      v-if="review.error.value && !review.context.value"
      aria-labelledby="phenopacket-review-error-title"
    >
      <h1 id="phenopacket-review-error-title" class="text-h5 mb-3">
        {{ privateNotFound ? 'Review workspace not found' : 'Unable to load review workspace' }}
      </h1>
      <p v-if="privateNotFound">This review workspace is unavailable or you do not have access.</p>
      <v-alert v-else type="error" variant="tonal" role="alert">
        {{ review.error.value.message || 'The review context could not be loaded.' }}
        <template #append>
          <v-btn
            data-testid="retry-review-context"
            class="touch-target"
            variant="text"
            @click="loadWorkspace"
          >
            Retry
          </v-btn>
        </template>
      </v-alert>
    </section>

    <section
      v-else-if="!review.context.value"
      aria-labelledby="phenopacket-review-loading-title"
      :aria-busy="review.loading.value"
    >
      <h1 id="phenopacket-review-loading-title" class="text-h5 mb-2">Phenopacket review</h1>
      <p class="text-body-2 text-medium-emphasis">Loading the locked review workspace.</p>
      <div class="workspace-skeleton" aria-hidden="true">
        <v-skeleton-loader data-testid="workspace-skeleton" type="heading, paragraph@3" />
        <v-skeleton-loader type="article, actions" />
      </div>
    </section>

    <template v-else>
      <ReviewHeader :context="review.context.value" :return-to="queueReturnPath" class="mb-5" />

      <div class="review-workspace">
        <div data-testid="content-column" class="review-content-column">
          <v-tabs v-model="activeView" class="content-tabs mb-4" show-arrows>
            <v-tab class="touch-target" value="changes">Changes</v-tab>
            <v-tab class="touch-target" value="candidate">Candidate</v-tab>
            <v-tab class="touch-target" value="json">Raw JSON</v-tab>
            <v-tab class="touch-target" value="history">History</v-tab>
          </v-tabs>

          <div class="content-view">
            <SemanticDiff
              v-if="activeView === 'changes'"
              :changes="review.context.value.semantic_changes"
              :baseline="review.context.value.baseline"
            />
            <CandidateSnapshot
              v-else-if="activeView === 'candidate'"
              :candidate="review.context.value.candidate"
            />
            <section v-else-if="activeView === 'json'" aria-labelledby="candidate-json-title">
              <h2 id="candidate-json-title" class="text-h6 mb-3">Complete candidate JSON</h2>
              <pre data-testid="raw-json" class="raw-json">{{ candidateJson }}</pre>
            </section>
            <section v-else aria-labelledby="revision-history-title">
              <h2 id="revision-history-title" class="text-h6">Revision history</h2>
              <HistoryTab
                :entries="history.historyEntries.value"
                :loading="history.historyLoading.value"
                :error="history.historyError.value"
              />
            </section>
          </div>
        </div>

        <aside
          data-testid="review-right-rail"
          class="review-right-rail"
          aria-label="Review discussion and decisions"
        >
          <section class="rail-section">
            <ReviewIssuesPanel
              :issues="review.context.value.issues"
              :record-id="review.context.value.record_id"
              :record-revision="review.context.value.record_revision"
              :candidate-revision-id="review.context.value.candidate.id"
              :create-issue-capability="createIssueCapability"
              :reload="review.reload"
              :live-message="review.liveMessage.value"
            />
          </section>

          <section
            class="rail-section discussion-rail-section"
            aria-labelledby="discussion-summary-title"
          >
            <h2 id="discussion-summary-title" class="text-h6 mb-3">Discussion summary</h2>
            <dl class="discussion-counts">
              <div>
                <dt>Ordinary comments</dt>
                <dd>{{ review.context.value.discussion_summary.ordinary_comments }}</dd>
              </div>
              <div>
                <dt>Blocking issues</dt>
                <dd>{{ review.context.value.discussion_summary.blocking_issues }}</dd>
              </div>
              <div>
                <dt>Open blocking issues</dt>
                <dd>{{ review.context.value.discussion_summary.open_blocking_issues }}</dd>
              </div>
            </dl>
          </section>

          <section
            data-testid="decision-rail-section"
            class="rail-section decision-rail-section mobile-safe-decision"
          >
            <ReviewActionPanel
              :context="review.context.value"
              :reload="review.reload"
              :on-completed="onDecisionCompleted"
            />
          </section>
        </aside>
      </div>
    </template>

    <span role="status" aria-live="polite" class="sr-only">{{ liveAnnouncement }}</span>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';

import HistoryTab from '@/components/phenopacket/HistoryTab.vue';
import CandidateSnapshot from '@/components/review/CandidateSnapshot.vue';
import ReviewActionPanel from '@/components/review/ReviewActionPanel.vue';
import ReviewHeader from '@/components/review/ReviewHeader.vue';
import ReviewIssuesPanel from '@/components/review/ReviewIssuesPanel.vue';
import SemanticDiff from '@/components/review/SemanticDiff.vue';
import { usePhenopacketState } from '@/composables/usePhenopacketState';
import { useReviewContext } from '@/composables/useReviewContext';

const route = useRoute();
const phenopacketId = computed(() => String(route.params.phenopacket_id || ''));
const review = useReviewContext(phenopacketId);
const history = usePhenopacketState(phenopacketId.value);

const activeView = ref('changes');
const mutationMessage = ref('');

const queueReturnPath = computed(() => {
  const value = route.query.return_to;
  return typeof value === 'string' ? value : '';
});
const privateNotFound = computed(() => review.error.value?.response?.status === 404);
const createIssueCapability = computed(
  () =>
    review.context.value?.capabilities?.find((item) => item.action === 'create_issue') || {
      action: 'create_issue',
      allowed: false,
      blocked_by: ['review_closed'],
    }
);
const candidateJson = computed(() =>
  JSON.stringify(review.context.value?.candidate?.content || {}, null, 2)
);
const liveAnnouncement = computed(() => mutationMessage.value || review.liveMessage.value || '');

async function refreshHistory() {
  try {
    await history.loadHistory();
  } catch (historyError) {
    window.logService?.error?.('Failed to refresh review history', {
      recordId: phenopacketId.value,
      error: historyError?.message,
    });
  }
}

async function loadWorkspace() {
  mutationMessage.value = '';
  const loaded = await review.load();
  if (loaded) await refreshHistory();
}

async function onDecisionCompleted({ action }) {
  await refreshHistory();
  const count = review.context.value?.discussion_summary?.open_blocking_issues;
  const issueCopy = Number.isInteger(count)
    ? ` ${count} open blocking issue${count === 1 ? '' : 's'} remain.`
    : '';
  mutationMessage.value = `Review decision saved (${action.replaceAll('_', ' ')}).${issueCopy}`;
}

onMounted(loadWorkspace);
</script>

<style scoped>
.review-page {
  max-width: 1600px;
}

.workspace-skeleton,
.review-content-column,
.review-right-rail {
  min-width: 0;
}

.workspace-skeleton,
.review-right-rail {
  display: grid;
  gap: 1rem;
}

.review-workspace {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: minmax(0, 2fr) minmax(19rem, 1fr);
}

.review-right-rail {
  align-self: start;
  position: sticky;
  top: 1rem;
}

.content-tabs {
  overflow-x: auto;
}

.touch-target {
  min-height: 44px;
}

.content-view,
.rail-section {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgb(var(--v-theme-surface-variant));
  border-radius: 8px;
  padding: 1rem;
}

.rail-section :deep(.v-btn) {
  min-height: 44px;
}

.raw-json {
  margin: 0;
  max-width: 100%;
  overflow: auto;
  white-space: pre;
}

.discussion-counts {
  display: grid;
  gap: 0.75rem;
  margin: 0;
}

.discussion-counts div {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.discussion-counts dd {
  font-weight: 700;
  margin: 0;
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

@media (max-width: 959px) {
  .review-page {
    padding-left: 0.75rem;
    padding-right: 0.75rem;
  }

  .review-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .review-right-rail {
    position: static;
  }

  .mobile-safe-decision {
    bottom: 0;
    order: 2;
    padding-bottom: calc(1rem + env(safe-area-inset-bottom));
    position: sticky;
    z-index: 2;
  }

  .discussion-rail-section {
    order: 3;
  }
}
</style>
