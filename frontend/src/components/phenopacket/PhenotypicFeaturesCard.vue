<!-- src/components/phenopacket/PhenotypicFeaturesCard.vue -->
<template>
  <!-- eslint-disable vue/html-closing-bracket-newline -->
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-green-lighten-5">
      <v-icon left color="success" size="small"> mdi-medical-bag </v-icon>
      Phenotypic Features ({{ headerCountLabel }})
    </v-card-title>
    <v-card-text class="pa-3">
      <v-alert v-if="features.length === 0" type="info" density="compact">
        No phenotypic features recorded
      </v-alert>

      <!-- Compact chip-based display. Renders BOTH present and excluded
           features -- excluded ones are a stronger clinical claim than
           silence and must be visible and counted (curation console plan
           Task 9), visually distinguished via the same present=green/
           excluded=error semantic-color convention
           PhenotypicFeaturesSection.vue's tri-state editor already uses,
           so no hardcoded bg-*-lighten-* is introduced (design spec §5). -->
      <div v-else class="feature-chips">
        <v-tooltip
          v-for="(feature, index) in features"
          :key="index"
          location="top"
          max-width="320"
          :aria-label="tooltipAriaLabel(feature)"
        >
          <template #activator="{ props }">
            <v-chip
              v-bind="props"
              :href="getHpoUrl(feature.type.id)"
              target="_blank"
              rel="noopener noreferrer"
              :color="feature.excluded ? 'error' : 'green'"
              variant="tonal"
              size="small"
              class="feature-chip"
              label
              :aria-label="chipAriaLabel(feature)"
            >
              <!-- Excluded indicator -->
              <v-icon v-if="feature.excluded" size="x-small" class="mr-1" aria-hidden="true">
                mdi-minus-circle
              </v-icon>

              <!-- Feature name -->
              <span
                class="feature-name"
                :class="{ 'text-decoration-line-through': feature.excluded }"
              >
                {{ feature.type.label }}
              </span>
              <span v-if="feature.excluded" class="feature-excluded-label text-caption ml-1">
                (excluded)
              </span>
              <span
                v-for="(evidence, evidenceIndex) in feature.evidence || []"
                :key="`chip-evidence-${evidenceIndex}`"
                class="feature-evidence text-caption ml-1"
              >
                {{ evidence.reference?.id }}
              </span>

              <!-- Modifier indicators -->
              <template v-if="feature.modifiers && feature.modifiers.length > 0">
                <v-icon
                  v-if="hasBilateralModifier(feature)"
                  size="x-small"
                  class="ml-1"
                  title="Bilateral"
                >
                  mdi-arrow-left-right
                </v-icon>
                <span v-if="getOtherModifiersCount(feature) > 0" class="modifier-count ml-1">
                  +{{ getOtherModifiersCount(feature) }}
                </span>
              </template>

              <!-- Severity indicator -->
              <v-icon
                v-if="feature.severity"
                size="x-small"
                class="ml-1"
                :color="getSeverityColor(feature.severity)"
              >
                {{ getSeverityIcon(feature.severity) }}
              </v-icon>
            </v-chip>
          </template>

          <!-- Tooltip content with full details -->
          <div class="tooltip-content">
            <div class="tooltip-header">
              <strong class="tooltip-title">{{ feature.type.label }}</strong>
              <span class="tooltip-id">{{ feature.type.id }}</span>
            </div>

            <div v-if="feature.excluded" class="tooltip-row">
              <v-icon size="x-small" class="mr-1" color="error">mdi-minus-circle</v-icon>
              <span>Excluded (tested, not observed)</span>
            </div>

            <div v-if="feature.onset" class="tooltip-row">
              <v-icon size="x-small" class="mr-1">mdi-calendar-start</v-icon>
              <span>{{ formatOnset(feature.onset) }}</span>
            </div>

            <div v-if="feature.severity" class="tooltip-row">
              <v-icon size="x-small" class="mr-1">mdi-signal</v-icon>
              <span>Severity: {{ feature.severity.label || feature.severity.id }}</span>
            </div>

            <div v-if="hasModifiers(feature)" class="tooltip-row">
              <v-icon size="x-small" class="mr-1">mdi-tag-multiple</v-icon>
              <span>{{ getModifiersText(feature) }}</span>
            </div>

            <div
              v-for="(evidence, evidenceIndex) in feature.evidence || []"
              :key="`evidence-${evidenceIndex}`"
              class="tooltip-row"
            >
              <v-icon size="x-small" class="mr-1">mdi-book-open-variant</v-icon>
              <span>
                Evidence:
                {{ evidence.evidenceCode?.label || evidence.evidenceCode?.id || 'Source' }}
                <a
                  v-if="evidence.reference?.id"
                  :href="evidenceUrl(evidence.reference.id)"
                  target="_blank"
                  rel="noopener noreferrer"
                  >{{ evidence.reference.id }}</a
                >
              </span>
            </div>

            <div class="tooltip-footer">
              <v-icon size="x-small" class="mr-1">mdi-open-in-new</v-icon>
              Click to view in HPO Browser
            </div>
          </div>
        </v-tooltip>
      </div>

      <!-- Summary stats row - only show if there's meaningful data -->
      <div v-if="hasSummaryData" class="summary-row mt-3 pt-2 border-t">
        <div class="d-flex flex-wrap gap-2 text-caption text-medium-emphasis">
          <span v-if="onsetCategories.prenatal > 0">
            <v-icon size="x-small" class="mr-1">mdi-baby-carriage</v-icon>
            {{ onsetCategories.prenatal }} prenatal
          </span>
          <span v-if="onsetCategories.congenital > 0">
            <v-icon size="x-small" class="mr-1">mdi-baby</v-icon>
            {{ onsetCategories.congenital }} congenital
          </span>
          <span v-if="onsetCategories.postnatal > 0">
            <v-icon size="x-small" class="mr-1">mdi-calendar</v-icon>
            {{ onsetCategories.postnatal }} postnatal
          </span>
          <span v-if="modifierSummary.bilateral > 0">
            <v-icon size="x-small" class="mr-1">mdi-arrow-left-right</v-icon>
            {{ modifierSummary.bilateral }} bilateral
          </span>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
// Typography tokens imported for reference - using local method implementations

export default {
  name: 'PhenotypicFeaturesCard',
  props: {
    features: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    presentFeatures() {
      return this.features.filter((feature) => !feature.excluded);
    },

    excludedFeatures() {
      return this.features.filter((feature) => feature.excluded);
    },

    // Curation console plan Task 9: the header count must equal what's
    // actually rendered below (ALL features, present + excluded) rather
    // than silently dropping excluded ones from both the DOM and the count,
    // as it did before this task.
    headerCountLabel() {
      if (this.excludedFeatures.length === 0) return `${this.presentFeatures.length}`;
      return `${this.presentFeatures.length} present, ${this.excludedFeatures.length} excluded`;
    },

    onsetCategories() {
      const categories = { prenatal: 0, congenital: 0, postnatal: 0, unknown: 0 };

      this.presentFeatures.forEach((feature) => {
        if (!feature.onset) {
          categories.unknown++;
          return;
        }

        const onsetText = this.formatOnset(feature.onset).toLowerCase();
        if (onsetText.includes('prenatal') || onsetText.includes('fetal')) {
          categories.prenatal++;
        } else if (onsetText.includes('congenital') || onsetText.includes('birth')) {
          categories.congenital++;
        } else if (
          onsetText.includes('postnatal') ||
          onsetText.includes('year') ||
          onsetText.includes('month')
        ) {
          categories.postnatal++;
        } else {
          categories.unknown++;
        }
      });

      return categories;
    },

    modifierSummary() {
      let bilateral = 0;

      this.presentFeatures.forEach((feature) => {
        if (feature.modifiers) {
          if (
            feature.modifiers.some((m) =>
              (m.label || m.id || '').toLowerCase().includes('bilateral')
            )
          ) {
            bilateral++;
          }
        }
      });

      return { bilateral };
    },

    hasSummaryData() {
      return (
        this.onsetCategories.prenatal > 0 ||
        this.onsetCategories.congenital > 0 ||
        this.onsetCategories.postnatal > 0 ||
        this.modifierSummary.bilateral > 0
      );
    },
  },
  methods: {
    // Curation console plan Task 9: excluded features must be unmistakable
    // to assistive tech too, not just visually (strikethrough + icon +
    // "(excluded)" label are sighted-only cues).
    tooltipAriaLabel(feature) {
      const base = `${feature.type.label} - ${feature.type.id}`;
      return feature.excluded ? `${base} (excluded)` : base;
    },

    chipAriaLabel(feature) {
      const base = `${feature.type.label} (${feature.type.id})`;
      return feature.excluded
        ? `${base} - Excluded - Click to view in HPO Browser`
        : `${base} - Click to view in HPO Browser`;
    },

    getHpoUrl(hpoId) {
      if (hpoId && hpoId.startsWith('HP:')) {
        return `https://hpo.jax.org/app/browse/term/${hpoId}`;
      }
      return '#';
    },

    evidenceUrl(referenceId) {
      if (referenceId.startsWith('PMID:')) {
        return `https://pubmed.ncbi.nlm.nih.gov/${referenceId.slice(5)}/`;
      }
      if (referenceId.startsWith('DOI:')) return `https://doi.org/${referenceId.slice(4)}`;
      return '#';
    },

    hasBilateralModifier(feature) {
      if (!feature.modifiers) return false;
      return feature.modifiers.some((m) =>
        (m.label || m.id || '').toLowerCase().includes('bilateral')
      );
    },

    getOtherModifiersCount(feature) {
      if (!feature.modifiers) return 0;
      const otherMods = feature.modifiers.filter(
        (m) => !(m.label || m.id || '').toLowerCase().includes('bilateral')
      );
      return otherMods.length;
    },

    hasModifiers(feature) {
      return feature.modifiers && feature.modifiers.length > 0;
    },

    getModifiersText(feature) {
      if (!feature.modifiers) return '';
      return feature.modifiers.map((m) => m.label || m.id).join(', ');
    },

    getSeverityColor(severity) {
      const label = (severity.label || severity.id || '').toLowerCase();
      if (label.includes('severe')) return 'error';
      if (label.includes('moderate')) return 'warning';
      if (label.includes('mild')) return 'success';
      return 'grey';
    },

    getSeverityIcon(severity) {
      const label = (severity.label || severity.id || '').toLowerCase();
      if (label.includes('severe')) return 'mdi-alert-circle';
      if (label.includes('moderate')) return 'mdi-alert';
      if (label.includes('mild')) return 'mdi-information';
      return 'mdi-circle-small';
    },

    formatOnset(onset) {
      const extractAgeDuration = (age) => {
        if (typeof age === 'string') return age;
        if (age.iso8601duration) return age.iso8601duration;
        if (age.ontologyClass) return null;
        return null;
      };

      if (onset.ontologyClass && onset.age) {
        const classification = (onset.ontologyClass.label || onset.ontologyClass.id).toLowerCase();
        const ageDuration = extractAgeDuration(onset.age);
        if (ageDuration) {
          const formattedAge = this.formatISO8601Duration(ageDuration);
          return `${classification}, age ${formattedAge}`;
        }
        return classification;
      }

      if (onset.iso8601duration) {
        return `age ${this.formatISO8601Duration(onset.iso8601duration)}`;
      }

      if (onset.age) {
        const ageDuration = extractAgeDuration(onset.age);
        if (ageDuration) {
          return `age ${this.formatISO8601Duration(ageDuration)}`;
        }
        if (onset.age.ontologyClass) {
          return onset.age.ontologyClass.label || onset.age.ontologyClass.id;
        }
        return 'Unknown';
      }

      if (onset.ontologyClass) {
        return onset.ontologyClass.label || onset.ontologyClass.id;
      }

      return 'Unknown';
    },

    formatISO8601Duration(duration) {
      const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?/;
      const matches = duration.match(regex);
      if (!matches) return duration;

      const parts = [];
      if (matches[1]) parts.push(`${matches[1]}y`);
      if (matches[2]) parts.push(`${matches[2]}m`);
      if (matches[3]) parts.push(`${matches[3]}d`);

      return parts.join(' ') || duration;
    },
  },
};
</script>

<style scoped>
/**
 * Typography tokens applied via CSS custom properties.
 * Values sourced from cardStyles.js TYPOGRAPHY and COLORS.
 */
.feature-chips {
  /* Typography tokens - consistent with InterpretationsCard */
  --font-size-xs: 10px;
  --font-size-sm: 11px;
  --font-size-base: 12px;
  --font-size-md: 13px;
  --font-mono: 'Roboto Mono', 'Consolas', 'Monaco', monospace;

  /* Color tokens */
  --color-text-primary: rgba(0, 0, 0, 0.87);
  --color-text-secondary: rgba(0, 0, 0, 0.6);

  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.feature-chip {
  cursor: pointer;
  transition:
    transform 0.1s,
    box-shadow 0.1s;
}

.feature-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.feature-name {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modifier-count {
  font-size: var(--font-size-xs);
  font-weight: 600;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  padding: 1px 4px;
}

.tooltip-content {
  padding: 4px 0;
}

.tooltip-header {
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.tooltip-title {
  display: block;
  font-size: var(--font-size-md);
  line-height: 1.3;
}

.tooltip-id {
  display: inline-block;
  margin-top: 4px;
  font-size: var(--font-size-xs);
  font-family: var(--font-mono);
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
  padding: 2px 6px;
  opacity: 0.85;
}

.tooltip-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 4px;
  font-size: var(--font-size-base);
}

.tooltip-footer {
  display: flex;
  align-items: center;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  font-size: var(--font-size-sm);
  opacity: 0.7;
}

.summary-row {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.border-t {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.gap-2 {
  gap: 12px;
}
</style>
