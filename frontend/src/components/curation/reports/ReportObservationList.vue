<template>
  <nav aria-label="Report observations" class="report-list">
    <h2 class="text-h6 mb-3">Source reports</h2>
    <ul>
      <li v-for="observation in observations" :key="observation.observationId">
        <button
          type="button"
          :aria-current="observation.observationId === selectedId ? 'true' : undefined"
          :class="{ selected: observation.observationId === selectedId }"
          @click="$emit('select', observation.observationId)"
        >
          <span class="report-list__title">{{ observation.identifiers?.reportId }}</span>
          <span>{{ publicationLabel(observation.publication) }}</span>
          <span>{{ observation.publication?.publicationType?.value || 'Type not reported' }}</span>
          <span>{{ completeness(observation) }}</span>
          <span v-if="conflictCount(observation)">
            {{ conflictCount(observation) }}
            {{ conflictCount(observation) === 1 ? 'conflict' : 'conflicts' }}
          </span>
          <span v-if="observation.observationId === dirtyId" class="report-list__dirty">
            Unsaved
          </span>
        </button>
      </li>
    </ul>
  </nav>
</template>

<script setup>
import { assessmentCompleteness, conflictCandidates } from '@/utils/curationAdapters';

const props = defineProps({
  observations: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  dirtyId: { type: String, default: null },
  issues: { type: Array, default: () => [] },
  corrections: { type: Array, default: () => [] },
});

defineEmits(['select']);

function publicationLabel(publication) {
  return (
    [
      publication?.pmid ? `PMID:${publication.pmid}` : '',
      publication?.doi ? `DOI:${publication.doi}` : '',
    ]
      .filter(Boolean)
      .join(' · ') || 'Publication not identified'
  );
}

function completeness(observation) {
  const result = assessmentCompleteness(observation.phenotypes);
  return `${result.filled}/${result.total} phenotypes`;
}

function conflictCount(observation) {
  return props.issues.filter(
    (issue) =>
      issue.observationId === observation.observationId ||
      conflictCandidates(issue, [observation], props.corrections).length > 0
  ).length;
}
</script>

<style scoped>
.report-list ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.report-list button {
  display: grid;
  gap: 3px;
  width: 100%;
  min-height: 44px;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  background: transparent;
  color: inherit;
  text-align: left;
}

.report-list button.selected {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.report-list__title {
  font-weight: 700;
}

.report-list__dirty {
  color: rgb(var(--v-theme-warning));
  font-weight: 700;
}
</style>
