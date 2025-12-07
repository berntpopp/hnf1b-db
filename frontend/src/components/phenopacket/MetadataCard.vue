<!-- src/components/phenopacket/MetadataCard.vue -->
<template>
  <v-card outlined>
    <v-expansion-panels v-model="expanded" variant="accordion">
      <v-expansion-panel value="metadata">
        <v-expansion-panel-title class="text-subtitle-1 py-2 bg-grey-lighten-4">
          <v-icon color="grey-darken-2" size="small" class="mr-2"> mdi-information-outline </v-icon>
          <span>Metadata</span>
          <template #actions="{ expanded }">
            <v-icon :icon="expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
          </template>
        </v-expansion-panel-title>
        <v-expansion-panel-text class="pa-0">
          <v-list density="compact" class="pa-2">
            <v-list-item v-if="metaData.created">
              <v-list-item-title class="font-weight-bold"> Created </v-list-item-title>
              <v-list-item-subtitle>
                {{ formatDate(metaData.created) }}
                <span v-if="metaData.createdBy" class="ml-2 text-grey">
                  by {{ metaData.createdBy }}
                </span>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="allReviewers.length > 0">
              <v-list-item-title class="font-weight-bold"> Reviewed By </v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  v-for="(reviewer, index) in allReviewers"
                  :key="index"
                  size="small"
                  color="purple-lighten-4"
                  variant="flat"
                  class="mr-1 mb-1"
                >
                  <v-icon left size="x-small">mdi-account-check</v-icon>
                  {{ reviewer }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item v-if="metaData.phenopacketSchemaVersion">
              <v-list-item-title class="font-weight-bold"> Schema Version </v-list-item-title>
              <v-list-item-subtitle>
                {{ metaData.phenopacketSchemaVersion }}
              </v-list-item-subtitle>
            </v-list-item>

            <v-divider
              v-if="metaData.externalReferences && metaData.externalReferences.length > 0"
              class="my-2"
            />

            <v-list-item
              v-if="metaData.externalReferences && metaData.externalReferences.length > 0"
            >
              <v-list-item-title class="font-weight-bold mb-2">
                External References ({{ metaData.externalReferences.length }})
              </v-list-item-title>
              <v-list>
                <v-list-item
                  v-for="(ref, index) in metaData.externalReferences"
                  :key="index"
                  density="compact"
                >
                  <v-chip
                    :href="formatExternalReferenceUrl(ref)"
                    target="_blank"
                    color="blue"
                    size="small"
                    variant="flat"
                    class="mr-2"
                  >
                    <v-icon left size="small"> mdi-open-in-new </v-icon>
                    {{ ref.id }}
                  </v-chip>
                  <span class="text-caption">
                    {{ ref.description }}
                    <span v-if="publicationYears[ref.id]" class="text-grey-darken-1">
                      ({{ publicationYears[ref.id] }})
                    </span>
                    <v-chip
                      v-if="ref.reference"
                      color="purple-lighten-4"
                      size="x-small"
                      variant="flat"
                      class="ml-2"
                    >
                      {{ ref.reference }}
                    </v-chip>
                  </span>
                </v-list-item>
              </v-list>
            </v-list-item>

            <v-divider v-if="metaData.updates && metaData.updates.length > 0" class="my-2" />

            <v-list-item v-if="enhancedUpdates.length > 0">
              <v-list-item-title class="font-weight-bold mb-2">
                Publication Timeline ({{ enhancedUpdates.length }})
              </v-list-item-title>
              <v-timeline density="compact" side="end" align="start">
                <v-timeline-item
                  v-for="(update, index) in enhancedUpdates"
                  :key="index"
                  dot-color="primary"
                  size="small"
                >
                  <template #opposite>
                    <div class="text-caption text-grey">
                      {{ formatDate(update.timestamp) }}
                    </div>
                  </template>
                  <div>
                    <!-- Publication Info -->
                    <div v-if="update.pmid" class="mb-2">
                      <v-chip
                        :to="`/publications/${update.pmid.number}`"
                        color="blue-lighten-4"
                        size="small"
                        variant="flat"
                        link
                      >
                        <v-icon left size="x-small">mdi-file-document</v-icon>
                        {{ update.pmid.id }}
                        <span v-if="publicationYears[update.pmid.id]" class="ml-1">
                          ({{ publicationYears[update.pmid.id] }})
                        </span>
                      </v-chip>
                    </div>

                    <!-- Reviewer Info -->
                    <div v-if="update.reviewer" class="text-caption text-grey mb-1">
                      <v-icon size="x-small" class="mr-1">mdi-account-edit</v-icon>
                      Reviewed by {{ update.reviewer }}
                    </div>

                    <!-- Comment -->
                    <div v-if="update.comment" class="text-body-2 mt-1">
                      {{ update.comment }}
                    </div>
                  </div>
                </v-timeline-item>
              </v-timeline>
            </v-list-item>

            <v-divider v-if="metaData.resources && metaData.resources.length > 0" class="my-2" />

            <v-list-item v-if="metaData.resources && metaData.resources.length > 0">
              <v-list-item-title class="font-weight-bold mb-2">
                Ontology Resources ({{ metaData.resources.length }})
              </v-list-item-title>
              <v-list>
                <v-list-item
                  v-for="(resource, index) in metaData.resources"
                  :key="index"
                  density="compact"
                >
                  <v-chip color="green" size="small" variant="flat" class="mr-2">
                    {{ resource.namespacePrefix }}
                  </v-chip>
                  <span class="text-body-2">
                    {{ resource.name }}
                    <span v-if="resource.version" class="text-caption text-grey">
                      ({{ resource.version }})
                    </span>
                  </span>
                </v-list-item>
              </v-list>
            </v-list-item>
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-card>
</template>

<script>
export default {
  name: 'MetadataCard',
  props: {
    metaData: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      expanded: null, // Start collapsed (null = no panel open)
      publicationYears: {}, // Map of PMID -> year
    };
  },
  computed: {
    allReviewers() {
      // Collect all unique reviewers from updates
      if (!this.metaData.updates || this.metaData.updates.length === 0) {
        return [];
      }

      const reviewers = new Set();
      this.metaData.updates.forEach((update) => {
        if (update.reviewer) {
          reviewers.add(update.reviewer);
        }
      });

      return Array.from(reviewers);
    },

    enhancedUpdates() {
      if (!this.metaData.updates) return [];

      // Get all PMIDs from external references (sorted)
      const pmids = (this.metaData.externalReferences || [])
        .filter((ref) => ref.id && ref.id.startsWith('PMID:'))
        .map((ref) => ({
          id: ref.id,
          number: this.getPmidNumber(ref.id),
        }));

      // Map updates with their corresponding PMID by array index
      // Backend creates both arrays in same iteration order (sorted chronologically)
      return this.metaData.updates.map((update, index) => {
        return {
          timestamp: update.timestamp,
          comment: update.comment,
          reviewer: update.reviewer,
          publication: update.publication,
          pmid: pmids[index] || null,
        };
      });
    },
  },
  mounted() {
    this.fetchPublicationYears();
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return 'N/A';
      try {
        return new Date(dateString).toLocaleString();
      } catch {
        return dateString;
      }
    },

    formatExternalReferenceUrl(ref) {
      // If reference is already a URL, use it
      if (ref.reference) {
        return ref.reference;
      }

      // Otherwise, construct URL based on ID type
      if (ref.id.startsWith('PMID:')) {
        const pmid = ref.id.replace('PMID:', '');
        return `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
      } else if (ref.id.startsWith('DOI:')) {
        const doi = ref.id.replace('DOI:', '');
        return `https://doi.org/${doi}`;
      }

      // Fallback to reference field or empty
      return ref.reference || '#';
    },

    getPmidNumber(pmidId) {
      // Extract number from "PMID:12345" → "12345"
      return pmidId.replace('PMID:', '');
    },

    async fetchPublicationYears() {
      // Extract PMIDs from external references
      if (!this.metaData.externalReferences) return;

      const pmidRefs = this.metaData.externalReferences.filter(
        (ref) => ref.id && ref.id.startsWith('PMID:')
      );

      if (pmidRefs.length === 0) return;

      // Fetch years for all PMIDs (batch request)
      const pmidNumbers = pmidRefs.map((ref) => this.getPmidNumber(ref.id));

      try {
        const response = await fetch(
          `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${pmidNumbers.join(',')}&retmode=json`
        );

        if (!response.ok) {
          window.logService.warn('Failed to fetch publication years from PubMed', {
            status: response.status,
          });
          return;
        }

        const data = await response.json();

        // Extract years from response
        const years = {};
        pmidRefs.forEach((ref) => {
          const pmidNum = this.getPmidNumber(ref.id);
          const pubmedData = data.result?.[pmidNum];

          if (pubmedData?.pubdate) {
            const yearMatch = pubmedData.pubdate.match(/^\d{4}/);
            if (yearMatch) {
              years[ref.id] = yearMatch[0];
            }
          }
        });

        this.publicationYears = years;

        window.logService.debug('Fetched publication years', {
          count: Object.keys(years).length,
        });
      } catch (error) {
        window.logService.error('Failed to fetch publication years', {
          error: error.message,
        });
      }
    },
  },
};
</script>

<style scoped>
/**
 * Typography tokens applied via CSS custom properties.
 * Values sourced from cardStyles.js TYPOGRAPHY and COLORS.
 */
.v-card {
  /* Typography tokens - consistent across all phenopacket cards */
  --font-size-xs: 10px;
  --font-size-sm: 11px;
  --font-size-base: 12px;
  --font-size-md: 13px;
  --font-mono: 'Roboto Mono', 'Consolas', 'Monaco', monospace;

  /* Color tokens */
  --color-text-primary: rgba(0, 0, 0, 0.87);
  --color-text-secondary: rgba(0, 0, 0, 0.6);
}

/* Timeline typography standardization */
.v-timeline :deep(.text-caption) {
  font-size: var(--font-size-sm) !important;
}

.v-timeline :deep(.text-body-2) {
  font-size: var(--font-size-base) !important;
}

/* List item typography */
.v-list-item-title {
  font-size: var(--font-size-md) !important;
  font-weight: 600 !important;
}

.v-list-item-subtitle {
  font-size: var(--font-size-base) !important;
  color: var(--color-text-secondary);
}

/* Chip sizing consistency - use small chips consistently */
.v-chip {
  font-size: var(--font-size-sm) !important;
}
</style>
