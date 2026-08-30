<template>
  <section class="semantic-diff" aria-labelledby="semantic-diff-title">
    <div class="semantic-diff__heading">
      <h2 id="semantic-diff-title" class="text-h6">Authoritative semantic changes</h2>
      <span v-if="baseline === null" class="baseline-label">New phenopacket</span>
    </div>

    <p v-if="changes.length === 0" class="text-body-2">No semantic changes reported.</p>
    <ul v-else class="semantic-diff__list">
      <li
        v-for="(change, index) in changes"
        :key="`${change.path}-${change.operation}-${index}`"
        class="semantic-change"
        :data-operation="change.operation"
        :aria-label="changeAriaLabel(change)"
      >
        <div class="semantic-change__header">
          <v-icon class="operation-icon" aria-hidden="true">
            {{ operationIcon(change.operation) }}
          </v-icon>
          <strong>{{ operationLabel(change.operation) }}</strong>
          <span>{{ change.section }}</span>
          <code class="semantic-change__path">{{ change.path }}</code>
        </div>
        <div class="semantic-change__values">
          <div>
            <span class="value-label">Before</span>
            <pre>{{ formatValue(change.before) }}</pre>
          </div>
          <div>
            <span class="value-label">After</span>
            <pre>{{ formatValue(change.after) }}</pre>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { sanitize } from '@/utils/sanitize';

defineProps({
  changes: { type: Array, default: () => [] },
  baseline: { type: Object, default: null },
});

const OPERATIONS = {
  added: { label: 'Added', icon: 'mdi-plus-circle-outline' },
  removed: { label: 'Removed', icon: 'mdi-minus-circle-outline' },
  changed: { label: 'Changed', icon: 'mdi-swap-horizontal' },
};

const operationLabel = (operation) => OPERATIONS[operation]?.label || 'Changed';
const operationIcon = (operation) => OPERATIONS[operation]?.icon || 'mdi-file-question-outline';
const changeAriaLabel = (change) =>
  `${operationLabel(change.operation)} at JSON pointer ${change.path}, section ${change.section}`;

function formatValue(value) {
  if (value === null || value === undefined) return 'Not present';
  if (typeof value === 'string') return sanitize(value);
  return JSON.stringify(
    value,
    (_key, nested) => (typeof nested === 'string' ? sanitize(nested) : nested),
    2
  );
}
</script>

<style scoped>
.semantic-diff__heading,
.semantic-change__header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.semantic-diff__list {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.semantic-change {
  border: 1px solid rgb(var(--v-theme-surface-variant));
  border-radius: 4px;
  margin-bottom: 0.75rem;
  padding: 0.75rem;
}

.semantic-change__values {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  margin-top: 0.75rem;
}

.semantic-change pre {
  margin: 0.25rem 0 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.value-label,
.baseline-label {
  font-weight: 600;
}
</style>
