<template>
  <section
    class="revision-compare side-by-side-compare"
    aria-labelledby="revision-compare-title"
    data-testid="revision-compare"
  >
    <div class="revision-compare__header mb-4">
      <div class="d-flex align-center justify-space-between flex-wrap ga-2">
        <div>
          <h2 id="revision-compare-title" class="text-h6 mb-1">Side-by-Side Revision Compare</h2>
          <p class="text-body-2 text-medium-emphasis mb-0">
            Compare the published baseline against candidate changes with side-by-side snapshots and
            highlighted JSON.
          </p>
        </div>

        <div class="d-flex align-center flex-wrap ga-2">
          <v-chip
            v-if="!baseline"
            color="info"
            size="small"
            variant="tonal"
            data-testid="compare-baseline-chip"
          >
            New phenopacket (No baseline)
          </v-chip>
          <v-chip
            v-else
            color="secondary"
            size="small"
            variant="tonal"
            data-testid="compare-baseline-chip"
          >
            Baseline: Head
          </v-chip>
          <v-chip color="primary" size="small" variant="tonal" data-testid="compare-candidate-chip">
            Candidate Revision
          </v-chip>
          <v-chip color="primary" size="small" variant="tonal">
            {{ changes.length }} change{{ changes.length === 1 ? '' : 's' }}
          </v-chip>
        </div>
      </div>

      <!-- Compare view mode selector -->
      <div class="d-flex align-center ga-2 mt-3">
        <span class="text-caption font-weight-medium text-medium-emphasis">View:</span>
        <v-btn-toggle
          v-model="compareMode"
          mandatory
          density="compact"
          color="primary"
          variant="outlined"
          data-testid="compare-mode-toggle"
        >
          <v-btn value="both" size="small">Both</v-btn>
          <v-btn value="snapshot" size="small">Clinical Snapshot</v-btn>
          <v-btn value="json" size="small">JSON Lines</v-btn>
        </v-btn-toggle>
      </div>
    </div>

    <!-- 1. Clinical Snapshot Side-by-Side -->
    <section
      v-if="compareMode === 'both' || compareMode === 'snapshot'"
      class="compare-section mb-6"
      data-testid="clinical-snapshot-compare"
      aria-labelledby="snapshot-compare-title"
    >
      <h3
        id="snapshot-compare-title"
        class="text-subtitle-1 font-weight-bold mb-3 d-flex align-center ga-2"
      >
        <v-icon size="small" color="primary">mdi-card-bulleted-outline</v-icon>
        Clinical Snapshot Comparison
      </h3>

      <div class="compare-columns">
        <div class="compare-column compare-column--baseline">
          <div
            class="column-header d-flex align-center justify-space-between mb-2 pb-1 border-bottom"
          >
            <span class="font-weight-bold text-subtitle-2">Baseline (Published Head)</span>
            <v-chip size="x-small" color="secondary" variant="tonal">Published</v-chip>
          </div>
          <CandidateSnapshot v-if="baseline" :candidate="baseline" />
          <div
            v-else
            data-testid="no-baseline-snapshot"
            class="empty-baseline-placeholder text-body-2 text-medium-emphasis pa-4 text-center"
          >
            No published baseline. This phenopacket is a new submission.
          </div>
        </div>

        <div class="compare-column compare-column--candidate">
          <div
            class="column-header d-flex align-center justify-space-between mb-2 pb-1 border-bottom"
          >
            <span class="font-weight-bold text-subtitle-2">Candidate Revision</span>
            <v-chip size="x-small" color="primary" variant="tonal">In Review</v-chip>
          </div>
          <CandidateSnapshot v-if="candidate" :candidate="candidate" />
        </div>
      </div>
    </section>

    <!-- 2. JSON Lines Side-by-Side with Highlights -->
    <section
      v-if="compareMode === 'both' || compareMode === 'json'"
      class="compare-section"
      data-testid="json-lines-compare"
      aria-labelledby="json-compare-title"
    >
      <h3
        id="json-compare-title"
        class="text-subtitle-1 font-weight-bold mb-3 d-flex align-center ga-2"
      >
        <v-icon size="small" color="primary">mdi-code-json</v-icon>
        JSON Lines Comparison (Changed Sections Highlighted)
      </h3>

      <div class="compare-columns">
        <div class="compare-column compare-column--baseline">
          <div
            class="column-header d-flex align-center justify-space-between mb-2 pb-1 border-bottom"
          >
            <span class="font-weight-bold text-subtitle-2">Baseline JSON</span>
            <span class="text-caption text-medium-emphasis">
              {{ baselineLines.length }} lines
            </span>
          </div>
          <div
            v-if="baselineLines.length > 0"
            data-testid="baseline-json-lines"
            class="json-code-container"
          >
            <div
              v-for="line in baselineLines"
              :key="line.lineNumber"
              class="json-line"
              :class="{
                'json-line--highlighted': line.isChanged,
                'json-line--removed': line.isChanged,
              }"
              :data-changed="line.isChanged"
            >
              <span class="json-line__number">{{ line.lineNumber }}</span>
              <span class="json-line__code">{{ line.text }}</span>
            </div>
          </div>
          <div
            v-else
            data-testid="no-baseline-json"
            class="empty-baseline-placeholder text-body-2 text-medium-emphasis pa-4 text-center"
          >
            No baseline JSON content.
          </div>
        </div>

        <div class="compare-column compare-column--candidate">
          <div
            class="column-header d-flex align-center justify-space-between mb-2 pb-1 border-bottom"
          >
            <span class="font-weight-bold text-subtitle-2">Candidate JSON</span>
            <span class="text-caption text-medium-emphasis">
              {{ candidateLines.length }} lines
            </span>
          </div>
          <div
            v-if="candidateLines.length > 0"
            data-testid="candidate-json-lines"
            class="json-code-container"
          >
            <div
              v-for="line in candidateLines"
              :key="line.lineNumber"
              class="json-line"
              :class="{
                'json-line--highlighted': line.isChanged,
                'json-line--added': line.isChanged,
              }"
              :data-changed="line.isChanged"
            >
              <span class="json-line__number">{{ line.lineNumber }}</span>
              <span class="json-line__code">{{ line.text }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import CandidateSnapshot from '@/components/review/CandidateSnapshot.vue';

const props = defineProps({
  baseline: { type: Object, default: null },
  candidate: { type: Object, required: true },
  changes: { type: Array, default: () => [] },
});

const compareMode = ref('both');

function escapeJsonPointerToken(token) {
  return String(token).replace(/~/g, '~0').replace(/\//g, '~1');
}

function serializeWithPaths(value, path = '', indent = 0, keyPrefix = '', comma = '') {
  const pad = '  '.repeat(indent);
  const out = [];

  if (value === null || typeof value !== 'object') {
    out.push({ text: `${pad}${keyPrefix}${JSON.stringify(value)}${comma}`, path });
    return out;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      out.push({ text: `${pad}${keyPrefix}[]${comma}`, path });
      return out;
    }
    out.push({ text: `${pad}${keyPrefix}[`, path });
    for (let i = 0; i < value.length; i += 1) {
      const childComma = i < value.length - 1 ? ',' : '';
      const childPath = `${path}/${i}`;
      out.push(...serializeWithPaths(value[i], childPath, indent + 1, '', childComma));
    }
    out.push({ text: `${pad}]${comma}`, path });
    return out;
  }

  const keys = Object.keys(value).filter((k) => value[k] !== undefined);
  if (keys.length === 0) {
    out.push({ text: `${pad}${keyPrefix}{}${comma}`, path });
    return out;
  }
  out.push({ text: `${pad}${keyPrefix}{`, path });
  for (let i = 0; i < keys.length; i += 1) {
    const k = keys[i];
    const childComma = i < keys.length - 1 ? ',' : '';
    const childPath = `${path}/${escapeJsonPointerToken(k)}`;
    const childPrefix = `${JSON.stringify(k)}: `;
    out.push(...serializeWithPaths(value[k], childPath, indent + 1, childPrefix, childComma));
  }
  out.push({ text: `${pad}}${comma}`, path });
  return out;
}

function computeHighlightedLines(obj, changes, isCandidate) {
  if (!obj) return [];
  const content = obj.content || obj;
  if (typeof content !== 'object' || Object.keys(content).length === 0) {
    return [];
  }

  const rawLines = serializeWithPaths(content);
  const activePaths = (changes || [])
    .filter((c) => {
      if (!c?.path) return false;
      if (isCandidate && c.operation === 'removed') return false;
      if (!isCandidate && c.operation === 'added') return false;
      return true;
    })
    .map((c) => c.path);

  return rawLines.map((entry, index) => {
    const isChanged =
      Boolean(entry.path) &&
      activePaths.some(
        (changePath) => entry.path === changePath || entry.path.startsWith(`${changePath}/`)
      );

    return {
      lineNumber: index + 1,
      text: entry.text,
      isChanged,
      operation: isChanged ? (isCandidate ? 'added' : 'removed') : null,
    };
  });
}

const baselineLines = computed(() => computeHighlightedLines(props.baseline, props.changes, false));

const candidateLines = computed(() =>
  computeHighlightedLines(props.candidate, props.changes, true)
);
</script>

<style scoped>
.compare-columns {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.compare-column {
  min-width: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 6px;
  padding: 0.75rem;
  background-color: rgb(var(--v-theme-surface));
}

.compare-column--baseline {
  border-color: rgba(var(--v-theme-secondary), 0.5);
}

.compare-column--candidate {
  border-color: rgba(var(--v-theme-primary), 0.6);
}

.empty-baseline-placeholder {
  border: 1px dashed rgba(var(--v-theme-outline), 0.3);
  border-radius: 4px;
}

.json-code-container {
  background-color: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-theme-outline), 0.15);
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  max-height: 28rem;
  overflow: auto;
  padding: 0.5rem 0;
}

.json-line {
  display: flex;
  padding: 0 0.5rem;
  white-space: pre;
}

.json-line--highlighted {
  font-weight: 600;
}

.json-line--added {
  background-color: rgba(var(--v-theme-success), 0.15);
}

.json-line--removed {
  background-color: rgba(var(--v-theme-error), 0.15);
}

/* Diff marker gutter so added/removed isn't conveyed by colour alone */
.json-line::before {
  content: ' ';
  width: 1ch;
  margin-right: 0.5ch;
  flex: none;
}
.json-line--added::before {
  content: '+';
}
.json-line--removed::before {
  content: '\2212';
}

.json-line__number {
  color: rgba(var(--v-theme-on-surface), 0.38);
  margin-right: 0.75rem;
  min-width: 2.25rem;
  text-align: right;
  user-select: none;
}

.json-line__code {
  overflow-wrap: normal;
  white-space: pre;
}

@media (max-width: 959px) {
  .compare-columns {
    grid-template-columns: 1fr;
  }
}
</style>
