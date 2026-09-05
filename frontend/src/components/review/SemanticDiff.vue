<template>
  <section class="semantic-diff" aria-labelledby="semantic-diff-title">
    <div class="semantic-diff__heading mb-3">
      <div class="d-flex align-center flex-wrap ga-2">
        <h2 id="semantic-diff-title" class="text-h6 mb-0">Authoritative semantic changes</h2>
        <v-chip
          v-if="baseline === null"
          color="info"
          size="small"
          variant="tonal"
          class="baseline-label"
        >
          New phenopacket
        </v-chip>
        <v-chip v-else color="teal" size="small" variant="tonal">
          {{ changes.length }} change{{ changes.length === 1 ? '' : 's' }} vs public head
        </v-chip>
      </div>

      <!-- Section filter chips -->
      <div v-if="availableSections.length > 1" class="d-flex flex-wrap ga-2 mt-2">
        <v-chip
          filter
          size="small"
          :variant="selectedSection === 'all' ? 'flat' : 'outlined'"
          :color="selectedSection === 'all' ? 'primary' : undefined"
          @click="selectedSection = 'all'"
        >
          All ({{ changes.length }})
        </v-chip>
        <v-chip
          v-for="sec in availableSections"
          :key="sec.name"
          filter
          size="small"
          :variant="selectedSection === sec.name ? 'flat' : 'outlined'"
          :color="selectedSection === sec.name ? 'primary' : undefined"
          @click="selectedSection = sec.name"
        >
          <v-icon start size="x-small">{{ sectionIcon(sec.name) }}</v-icon>
          {{ sec.name }} ({{ sec.count }})
        </v-chip>
      </div>
    </div>

    <p v-if="changes.length === 0" class="text-body-2 text-medium-emphasis">
      No semantic changes reported.
    </p>

    <div v-else class="semantic-diff__sections">
      <div v-for="group in filteredGroups" :key="group.section" class="section-group mb-5">
        <div class="section-group__header d-flex align-center ga-2 mb-2 pb-1 border-bottom">
          <v-icon size="small" color="primary">{{ sectionIcon(group.section) }}</v-icon>
          <h3 class="text-subtitle-1 font-weight-bold mb-0">{{ group.section }}</h3>
          <v-chip size="x-small" variant="tonal" color="primary">
            {{ group.items.length }} change{{ group.items.length === 1 ? '' : 's' }}
          </v-chip>
        </div>

        <ul class="semantic-diff__list">
          <li
            v-for="(change, index) in group.items"
            :key="`${change.path}-${change.operation}-${index}`"
            class="semantic-change"
            :data-operation="change.operation"
            :aria-label="changeAriaLabel(change)"
          >
            <div class="semantic-change__header">
              <v-chip
                size="small"
                variant="tonal"
                :color="operationColor(change.operation)"
                class="operation-chip"
              >
                <v-icon start size="x-small" class="operation-icon" aria-hidden="true">
                  {{ operationIcon(change.operation) }}
                </v-icon>
                <strong>{{ operationLabel(change.operation) }}</strong>
              </v-chip>
              <span class="change-section-tag text-caption text-medium-emphasis">{{
                change.section
              }}</span>
              <code class="semantic-change__path">{{ change.path }}</code>
            </div>

            <div class="semantic-change__values">
              <div class="value-block value-block--before">
                <span class="value-label text-caption">Before</span>
                <pre class="value-content">{{ formatValue(change.before) }}</pre>
              </div>
              <div class="value-block value-block--after">
                <span class="value-label text-caption">After</span>
                <pre class="value-content">{{ formatValue(change.after) }}</pre>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import { sanitize } from '@/utils/sanitize';

const props = defineProps({
  changes: { type: Array, default: () => [] },
  baseline: { type: Object, default: null },
});

const selectedSection = ref('all');

const OPERATIONS = {
  added: { label: 'Added', icon: 'mdi-plus-circle-outline', color: 'success' },
  removed: { label: 'Removed', icon: 'mdi-minus-circle-outline', color: 'error' },
  changed: { label: 'Changed', icon: 'mdi-swap-horizontal', color: 'info' },
};

const SECTION_ICONS = {
  Subject: 'mdi-account-outline',
  Phenotypes: 'mdi-format-list-checks',
  Diseases: 'mdi-virus-outline',
  'Variants/Interpretations': 'mdi-dna',
  Measurements: 'mdi-chart-bell-curve',
  Metadata: 'mdi-information-outline',
};

const operationLabel = (operation) => OPERATIONS[operation]?.label || 'Changed';
const operationIcon = (operation) => OPERATIONS[operation]?.icon || 'mdi-file-question-outline';
const operationColor = (operation) => OPERATIONS[operation]?.color || 'primary';
const sectionIcon = (section) => SECTION_ICONS[section] || 'mdi-tag-outline';

const changeAriaLabel = (change) =>
  `${operationLabel(change.operation)} at JSON pointer ${change.path}, section ${change.section}`;

const groupedChanges = computed(() => {
  const groups = {};
  for (const change of props.changes) {
    const sec = change.section || 'Metadata';
    if (!groups[sec]) {
      groups[sec] = [];
    }
    groups[sec].push(change);
  }
  return Object.entries(groups).map(([section, items]) => ({
    section,
    items,
  }));
});

const availableSections = computed(() =>
  groupedChanges.value.map((g) => ({
    name: g.section,
    count: g.items.length,
  }))
);

const filteredGroups = computed(() => {
  if (selectedSection.value === 'all') {
    return groupedChanges.value;
  }
  return groupedChanges.value.filter((g) => g.section === selectedSection.value);
});

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
.semantic-diff__heading {
  display: flex;
  flex-direction: column;
}

.semantic-diff__list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.semantic-change {
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 6px;
  margin-bottom: 0.75rem;
  padding: 0.75rem 1rem;
  background-color: rgb(var(--v-theme-surface));
  transition: border-color 0.15s ease-in-out;
}

.semantic-change[data-operation='added'] {
  border-color: rgba(var(--v-theme-success), 0.35);
  background-color: rgba(var(--v-theme-success), 0.02);
}

.semantic-change[data-operation='removed'] {
  border-color: rgba(var(--v-theme-error), 0.35);
  background-color: rgba(var(--v-theme-error), 0.02);
}

.semantic-change[data-operation='changed'] {
  border-color: rgba(var(--v-theme-info), 0.35);
  background-color: rgba(var(--v-theme-info), 0.02);
}

.semantic-change__header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.semantic-change__path {
  font-size: 0.8125rem;
  padding: 0.125rem 0.375rem;
  background-color: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 4px;
}

.semantic-change__values {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  margin-top: 0.75rem;
}

.value-block {
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  background-color: rgba(var(--v-theme-on-surface), 0.03);
  border: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.value-block--before {
  border-left: 2px solid rgba(var(--v-theme-error), 0.4);
}

.value-block--after {
  border-left: 2px solid rgba(var(--v-theme-success), 0.4);
}

.value-label {
  display: block;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.value-content {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  font-size: 0.8125rem;
  max-height: 16rem;
  overflow-y: auto;
}

.baseline-label {
  font-weight: 600;
}
</style>
