<!-- src/components/curation/CompletenessRail.vue -->
<!--
  Sticky completeness rail for the curation console (curation console design
  spec §2, §2.1, §5; plan Task 3). Shows an overall filled/total count and one
  row per CURATION_SECTIONS entry. Activating a row asks the parent to expand
  that section (via @navigate, since this component doesn't own any
  CurationSection refs) and scrolls to it itself.

  Phenotypes is deliberately excluded from the registry-driven computation:
  its completeness is dynamic per-case and is passed in verbatim via the
  `phenotypesCompleteness` prop (see curationFields.js docs).
-->
<template>
  <nav class="completeness-rail" aria-label="Curation completeness">
    <v-card variant="outlined" class="completeness-rail__card">
      <v-card-title class="text-subtitle-1 font-weight-medium">Completeness</v-card-title>
      <v-card-text>
        <div class="completeness-rail__overall mb-3">
          <span class="text-h6">{{ overall.filled }}/{{ overall.total }}</span>
          <span class="text-medium-emphasis ml-1">fields entered</span>
        </div>

        <ul class="completeness-rail__list">
          <li v-for="row in rows" :key="row.id">
            <button type="button" class="completeness-rail__row" @click="handleNavigate(row.id)">
              <span
                class="completeness-rail__glyph"
                :class="`completeness-rail__glyph--${row.status}`"
                aria-hidden="true"
              >
                {{ row.glyphChar }}
              </span>
              <span class="completeness-rail__label">{{ row.label }}</span>
              <span class="completeness-rail__count text-medium-emphasis">
                {{ row.filled }}/{{ row.total }}
              </span>
              <span class="visually-hidden">{{ row.statusLabel }}</span>
            </button>
          </li>
        </ul>

        <p class="completeness-rail__legend text-caption text-medium-emphasis mb-0">
          <span aria-hidden="true">&#10003;</span> complete &middot;
          <span aria-hidden="true">!</span> has a validation error &middot;
          <span aria-hidden="true">&mdash;</span> nothing entered yet
        </p>
      </v-card-text>
    </v-card>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { CURATION_SECTIONS, computeSectionCompleteness } from '@/utils/curationFields';
import { useAccessibleScroll } from '@/composables/useAccessibility';

const props = defineProps({
  phenopacket: { type: Object, required: true },
  phenotypesCompleteness: {
    type: Object,
    default: () => ({ filled: 0, total: 0 }),
  },
  errors: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(['navigate']);

const { scrollToElement } = useAccessibleScroll();

const rows = computed(() =>
  CURATION_SECTIONS.map((section) => {
    const completeness =
      section.id === 'phenotypes'
        ? props.phenotypesCompleteness
        : computeSectionCompleteness(props.phenopacket, section.id);
    const filled = completeness?.filled ?? 0;
    const total = completeness?.total ?? 0;
    const hasError = props.errors?.[section.id] === true;

    let status;
    let glyphChar;
    let statusLabel;
    if (hasError) {
      // Error overrides "complete" even if every field happens to be filled.
      status = 'error';
      glyphChar = '!';
      statusLabel = `${section.label}: has a validation error, ${filled} of ${total} fields entered`;
    } else if (total > 0 && filled === total) {
      status = 'complete';
      glyphChar = '✓';
      statusLabel = `${section.label}: complete, ${filled} of ${total} fields entered`;
    } else if (filled === 0) {
      status = 'empty';
      glyphChar = '—';
      statusLabel = `${section.label}: nothing entered yet`;
    } else {
      status = 'partial';
      glyphChar = '';
      statusLabel = `${section.label}: in progress, ${filled} of ${total} fields entered`;
    }

    return {
      id: section.id,
      label: section.label,
      filled,
      total,
      status,
      glyphChar,
      statusLabel,
    };
  })
);

const overall = computed(() =>
  rows.value.reduce(
    (acc, row) => ({ filled: acc.filled + row.filled, total: acc.total + row.total }),
    { filled: 0, total: 0 }
  )
);

function handleNavigate(sectionId) {
  // The parent owns the CurationSection refs (this rail doesn't), so it's
  // responsible for expanding a collapsed section; we do the scrolling
  // ourselves via the shared, prefers-reduced-motion-aware helper.
  emit('navigate', sectionId);
  scrollToElement(`#curation-section-${sectionId}`);
}
</script>

<style scoped>
.completeness-rail {
  width: 100%;
}

/* Sticky only at desktop widths, where the rail sits beside the form in its
   own column (per the 1440px mockup). At narrow widths the parent stacks
   this component above/below the form instead of beside it, so keeping the
   rail out of normal flow there would just be confusing. */
@media (min-width: 960px) {
  .completeness-rail {
    position: sticky;
    top: 16px;
  }
}

.completeness-rail__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.completeness-rail__row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.completeness-rail__row:hover,
.completeness-rail__row:focus-visible {
  background-color: rgba(128, 128, 128, 0.12);
}

.completeness-rail__row:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: -2px;
}

.completeness-rail__glyph {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 1.25em;
  font-weight: 700;
}

.completeness-rail__label {
  flex: 1 1 auto;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
