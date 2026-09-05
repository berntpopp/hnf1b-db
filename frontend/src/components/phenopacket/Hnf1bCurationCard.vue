<!-- src/components/phenopacket/Hnf1bCurationCard.vue -->
<template>
  <v-card variant="outlined" class="hnf1b-curation-card" data-testid="hnf1b-curation-card">
    <v-card-title
      class="text-subtitle-1 py-2 bg-teal-lighten-5 d-flex align-center justify-space-between flex-wrap ga-2"
    >
      <div class="d-flex align-center ga-2">
        <v-icon color="teal-darken-2" size="small">mdi-database-check-outline</v-icon>
        <span class="font-weight-medium">Curation Profile</span>
      </div>
      <v-chip
        v-if="curation.cohort"
        color="teal"
        size="small"
        variant="tonal"
        class="text-capitalize"
      >
        {{ formatCohort(curation.cohort) }}
      </v-chip>
    </v-card-title>

    <v-card-text class="pa-4">
      <div v-if="!hasCurationData" class="text-body-2 text-medium-emphasis">
        No HNF1B curation metadata recorded.
      </div>

      <dl v-else class="curation-metadata-grid">
        <div v-if="curation.publicationType">
          <dt class="text-caption text-medium-emphasis">Publication type</dt>
          <dd class="text-body-2 text-capitalize">{{ formatLabel(curation.publicationType) }}</dd>
        </div>

        <div v-if="curation.detectionMethod">
          <dt class="text-caption text-medium-emphasis">Detection method</dt>
          <dd class="text-body-2">{{ formatLabel(curation.detectionMethod) }}</dd>
        </div>

        <div v-if="curation.familyHistory">
          <dt class="text-caption text-medium-emphasis">Family history</dt>
          <dd class="text-body-2 text-capitalize">{{ formatLabel(curation.familyHistory) }}</dd>
        </div>

        <div v-if="curation.classificationSystem">
          <dt class="text-caption text-medium-emphasis">Classification system</dt>
          <dd class="text-body-2">
            {{ formatLabel(curation.classificationSystem) }}
            <span v-if="curation.classificationDate" class="text-caption text-medium-emphasis">
              ({{ curation.classificationDate }})
            </span>
          </dd>
        </div>

        <div v-if="curation.classificationComment">
          <dt class="text-caption text-medium-emphasis">Classification comment</dt>
          <dd class="text-body-2">{{ curation.classificationComment }}</dd>
        </div>

        <div v-if="curation.curatedBy">
          <dt class="text-caption text-medium-emphasis">Curated by</dt>
          <dd class="text-body-2">
            {{ curation.curatedBy }}
            <span v-if="curation.curatedAt" class="text-caption text-medium-emphasis">
              on {{ formatDate(curation.curatedAt) }}
            </span>
          </dd>
        </div>

        <div v-if="curation.caseComment" class="full-width">
          <dt class="text-caption text-medium-emphasis">Case notes</dt>
          <dd class="text-body-2 case-comment-text">{{ curation.caseComment }}</dd>
        </div>

        <div v-if="hasFlags" class="full-width mt-1 d-flex flex-wrap ga-2">
          <v-chip
            v-if="curation.duplicateCheck"
            color="success"
            size="x-small"
            variant="tonal"
            prepend-icon="mdi-check-decagram-outline"
          >
            Duplicate checked
          </v-chip>
          <v-chip
            v-if="curation.problematic"
            color="warning"
            size="x-small"
            variant="tonal"
            prepend-icon="mdi-alert-outline"
          >
            Marked as problematic
          </v-chip>
        </div>
      </dl>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  curation: {
    type: Object,
    default: () => ({}),
  },
});

const hasCurationData = computed(() => {
  const c = props.curation;
  if (!c || typeof c !== 'object') return false;
  return Object.keys(c).length > 0;
});

const hasFlags = computed(() =>
  Boolean(props.curation?.duplicateCheck || props.curation?.problematic)
);

function formatCohort(val) {
  if (!val) return '';
  return val === 'born' ? 'Born individual' : val === 'fetus' ? 'Fetus / Prenatal' : val;
}

function formatLabel(val) {
  if (!val) return '';
  return String(val).replaceAll('_', ' ');
}

function formatDate(val) {
  if (!val) return '';
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(val));
  } catch {
    return val;
  }
}
</script>

<style scoped>
.hnf1b-curation-card {
  border-color: rgba(var(--v-theme-outline), 0.2);
}

.curation-metadata-grid {
  display: grid;
  gap: 0.75rem 1rem;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  margin: 0;
}

.curation-metadata-grid dt {
  font-weight: 500;
  margin-bottom: 0.125rem;
}

.curation-metadata-grid dd {
  margin: 0;
}

.full-width {
  grid-column: 1 / -1;
}

.case-comment-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
