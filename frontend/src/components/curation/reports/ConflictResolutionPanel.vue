<template>
  <!-- eslint-disable vue/html-self-closing -->
  <section aria-labelledby="conflicts-heading">
    <h2 id="conflicts-heading" class="text-h6">Projection conflicts</h2>
    <p v-if="issues.length === 0">No unresolved projection conflicts.</p>
    <article v-for="issue in issues" :key="issue.conflictKey" class="conflict-card">
      <h3 class="text-subtitle-1">{{ issue.message || issue.conflictKey }}</h3>
      <div class="candidate-grid">
        <label
          v-for="candidate in candidates(issue)"
          :key="candidate.observationId"
          class="candidate"
        >
          <input
            type="checkbox"
            :disabled="readonly"
            :data-candidate="candidate.observationId"
            :checked="selection(issue).includes(candidate.observationId)"
            @change="toggle(issue, candidate.observationId, $event.target.checked)"
          />
          <strong>{{ candidate.reportId }}</strong>
          <span>{{ candidate.publication }}</span>
          <span>{{ candidate.reviewer }} {{ candidate.reviewedOn }}</span>
          <span>Raw: {{ candidate.raw }}</span>
          <span>Normalized: {{ candidate.value }}</span>
          <span v-for="evidence in candidate.evidence" :key="evidence.reference">
            Evidence: {{ evidence.reference }} ·
            {{ evidence.evidenceCode?.label || evidence.evidenceCode?.id }}
          </span>
        </label>
      </div>
      <label class="reason-field">
        Resolution reason
        <textarea
          :data-reason="issue.conflictKey"
          :value="reason(issue)"
          rows="2"
          :disabled="readonly"
          @input="reasons[issueKey(issue)] = $event.target.value"
        />
      </label>
      <p v-if="errors[issueKey(issue)]" role="alert" class="text-error">
        {{ errors[issueKey(issue)] }}
      </p>
      <button
        type="button"
        :data-resolve="issue.conflictKey"
        :disabled="readonly"
        @click="resolve(issue)"
      >
        Apply resolution
      </button>
    </article>
  </section>
</template>

<script setup>
import { reactive } from 'vue';

import { conflictCandidates } from '@/utils/curationAdapters';

const props = defineProps({
  issues: { type: Array, default: () => [] },
  observations: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
  corrections: { type: Array, default: () => [] },
});
const emit = defineEmits(['resolve']);
const selections = reactive({});
const reasons = reactive({});
const errors = reactive({});

const candidates = (issue) => conflictCandidates(issue, props.observations, props.corrections);
const issueKey = (issue) => `${issue.conflictKey}:${issue.candidateSetDigest}`;
const selection = (issue) => selections[issueKey(issue)] || [];
const reason = (issue) => reasons[issueKey(issue)] || '';

function toggle(issue, observationId, checked) {
  const current = selection(issue);
  selections[issueKey(issue)] = checked
    ? [...new Set([...current, observationId])]
    : current.filter((item) => item !== observationId);
}

function resolve(issue) {
  const selectedObservationIds = selection(issue);
  const rationale = reason(issue).trim();
  if (!rationale) {
    errors[issueKey(issue)] = 'Resolution reason is required';
    return;
  }
  if (selectedObservationIds.length === 0) {
    errors[issueKey(issue)] = 'Select at least one source report';
    return;
  }
  errors[issueKey(issue)] = '';
  emit('resolve', {
    conflictKey: issue.conflictKey,
    candidateSetDigest: issue.candidateSetDigest,
    strategy: 'select_observations',
    selectedObservationIds,
    reason: rationale,
  });
}
</script>

<style scoped>
.conflict-card {
  margin-block: 12px;
  padding: 16px;
  border: 1px solid rgb(var(--v-theme-warning));
  border-radius: 6px;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.candidate {
  display: grid;
  gap: 4px;
  min-height: 44px;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.reason-field {
  display: grid;
  gap: 4px;
  margin-block: 12px;
}

textarea {
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  color: inherit;
}

button {
  min-height: 44px;
  padding: 8px 14px;
}
</style>
