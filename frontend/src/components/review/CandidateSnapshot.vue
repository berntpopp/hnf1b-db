<template>
  <section class="candidate-snapshot" aria-labelledby="candidate-snapshot-title">
    <h2 id="candidate-snapshot-title" class="text-h6 mb-3">Candidate snapshot</h2>
    <p v-if="content.id" class="candidate-snapshot__identifier text-body-2 mb-3">
      <span class="font-weight-medium">Phenopacket ID:</span>
      <code data-testid="candidate-phenopacket-id">{{ content.id }}</code>
    </p>
    <div class="candidate-snapshot__cards">
      <SubjectCard v-if="content.subject" :subject="content.subject" />
      <PhenotypicFeaturesCard :features="content.phenotypicFeatures || []" />
      <DiseasesCard :diseases="content.diseases || []" />
      <InterpretationsCard :interpretations="content.interpretations || []" />
      <MeasurementsCard :measurements="content.measurements || []" />
      <MetadataCard v-if="content.metaData" :meta-data="content.metaData" />
    </div>

    <section v-if="hasRawContent" class="candidate-snapshot__raw mt-4" aria-labelledby="raw-title">
      <h3 id="raw-title" class="text-subtitle-1">Raw extension content</h3>
      <pre>{{ rawContent }}</pre>
    </section>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import DiseasesCard from '@/components/phenopacket/DiseasesCard.vue';
import InterpretationsCard from '@/components/phenopacket/InterpretationsCard.vue';
import MeasurementsCard from '@/components/phenopacket/MeasurementsCard.vue';
import MetadataCard from '@/components/phenopacket/MetadataCard.vue';
import PhenotypicFeaturesCard from '@/components/phenopacket/PhenotypicFeaturesCard.vue';
import SubjectCard from '@/components/phenopacket/SubjectCard.vue';
import { sanitize } from '@/utils/sanitize';

const props = defineProps({
  candidate: { type: Object, required: true },
});

const DISPLAYED_FIELDS = new Set([
  'id',
  'subject',
  'phenotypicFeatures',
  'diseases',
  'interpretations',
  'measurements',
  'metaData',
]);

const content = computed(() => props.candidate.content || props.candidate);
const unhandledContent = computed(() =>
  Object.fromEntries(Object.entries(content.value).filter(([key]) => !DISPLAYED_FIELDS.has(key)))
);
const hasRawContent = computed(() => Object.keys(unhandledContent.value).length > 0);
const rawContent = computed(() =>
  JSON.stringify(
    unhandledContent.value,
    (_key, value) => (typeof value === 'string' ? sanitize(value) : value),
    2
  )
);
</script>

<style scoped>
.candidate-snapshot__cards {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
}

.candidate-snapshot__raw {
  border: 1px solid rgb(var(--v-theme-surface-variant));
  border-radius: 4px;
  padding: 0.75rem;
}

.candidate-snapshot__raw pre {
  margin: 0.5rem 0 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
