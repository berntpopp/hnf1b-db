<template>
  <section aria-labelledby="projection-heading" class="projection-preview">
    <h2 id="projection-heading" class="text-h6">Canonical projection preview</h2>
    <p class="text-caption">Derived by the server; saving a report does not publish it.</p>
    <dl v-if="projection">
      <div>
        <dt>Subject</dt>
        <dd>{{ summary.subjectId }}</dd>
      </div>
      <div>
        <dt>Sex</dt>
        <dd>{{ summary.sex }}</dd>
      </div>
      <div>
        <dt>Phenotypes</dt>
        <dd>{{ summary.phenotypeCount }} phenotype{{ summary.phenotypeCount === 1 ? '' : 's' }}</dd>
      </div>
      <div>
        <dt>Variants</dt>
        <dd>{{ summary.variantCount }} variant{{ summary.variantCount === 1 ? '' : 's' }}</dd>
      </div>
      <div>
        <dt>Conflicts</dt>
        <dd>{{ summary.conflictCount }} conflict{{ summary.conflictCount === 1 ? '' : 's' }}</dd>
      </div>
      <div>
        <dt>References</dt>
        <dd>{{ summary.references.join(', ') || 'None' }}</dd>
      </div>
      <div>
        <dt>Output digest</dt>
        <dd class="digest">{{ summary.outputDigest }}</dd>
      </div>
    </dl>
    <details v-if="projection?.phenopacket">
      <summary>Inspect exact server-projected GA4GH JSON</summary>
      <pre>{{ JSON.stringify(projection.phenopacket, null, 2) }}</pre>
    </details>
    <p v-else>No projection is available.</p>
  </section>
</template>

<script setup>
import { computed } from 'vue';

import { projectionSummary } from '@/utils/curationAdapters';

const props = defineProps({ projection: { type: Object, default: null } });
const summary = computed(() => projectionSummary(props.projection));
</script>

<style scoped>
.projection-preview {
  padding: 16px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
}

dl {
  display: grid;
  gap: 6px;
}

dl div {
  display: grid;
  grid-template-columns: 120px 1fr;
}

dd {
  margin: 0;
}

.digest {
  overflow-wrap: anywhere;
  font-family: monospace;
}

pre {
  max-height: 420px;
  overflow: auto;
  padding: 8px;
  white-space: pre-wrap;
  background: rgba(var(--v-theme-on-surface), 0.05);
}
</style>
