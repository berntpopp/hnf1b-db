<!-- src/components/phenopacket/MetadataCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-grey-lighten-4">
      <v-icon left color="grey-darken-2" size="small"> mdi-information-outline </v-icon>
      Metadata
    </v-card-title>
    <v-card-text class="pa-2">
      <v-list density="compact">
        <v-list-item v-if="metaData.created">
          <v-list-item-title class="font-weight-bold"> Created </v-list-item-title>
          <v-list-item-subtitle>
            {{ formatDate(metaData.created) }}
            <span v-if="metaData.createdBy" class="ml-2 text-grey">
              by {{ metaData.createdBy }}
            </span>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="metaData.reviewer">
          <v-list-item-title class="font-weight-bold"> Reviewed By </v-list-item-title>
          <v-list-item-subtitle>
            {{ metaData.reviewer }}
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="metaData.comment">
          <v-list-item-title class="font-weight-bold"> Comment </v-list-item-title>
          <v-list-item-subtitle class="text-wrap">
            {{ metaData.comment }}
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

        <v-list-item v-if="metaData.externalReferences && metaData.externalReferences.length > 0">
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

        <v-list-item v-if="filteredUpdates.length > 0">
          <v-list-item-title class="font-weight-bold mb-2">
            Data Updates ({{ filteredUpdates.length }})
          </v-list-item-title>
          <v-timeline density="compact" side="end">
            <v-timeline-item
              v-for="(update, index) in filteredUpdates"
              :key="index"
              dot-color="blue"
              size="small"
            >
              <template #opposite>
                <span class="text-caption">{{ formatDate(update.timestamp) }}</span>
              </template>
              <div>
                <div v-if="update.pmid" class="text-body-2">
                  Data from
                  <v-chip
                    :to="`/publications/${getPmidNumber(update.pmid.id)}`"
                    color="blue"
                    size="small"
                    variant="flat"
                    class="mx-1"
                  >
                    <v-icon left size="x-small"> mdi-file-document </v-icon>
                    {{ update.pmid.id }}
                  </v-chip>
                </div>
                <div v-else class="text-body-2">
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
    </v-card-text>
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
      publicationYears: {}, // Map of PMID -> year
    };
  },
  mounted() {
    this.fetchPublicationYears();
  },
  computed: {
    filteredUpdates() {
      if (!this.metaData.updates) return [];

      // Get list of PMIDs from external references
      const pmids = (this.metaData.externalReferences || [])
        .filter((ref) => ref.id && ref.id.startsWith('PMID:'))
        .map((ref) => ({
          id: ref.id,
          url: ref.reference,
        }));

      return this.metaData.updates.map((update, index) => {
        /**
         * Map updates to PMIDs using array index.
         *
         * Backend migration creates updates and externalReferences in the same order,
         * so we can use array index to match them.
         *
         * Format: update.comment = "Data from pub123" → maps to pmids[index]
         *
         * This approach works because:
         * 1. Backend creates both arrays in the same iteration
         * 2. Order is preserved in database
         * 3. Handles cases where pub number doesn't match PMID number
         */

        // Map update to corresponding PMID by array index
        const pmid = pmids[index] || null;

        // Fallback: If no PMID found by index, try pattern matching (for backwards compatibility)
        if (!pmid && process.env.NODE_ENV === 'development') {
          const pubMatch = update.comment?.match(/pub(\d+)/i);
          console.debug(
            `No PMID found at index ${index} for update: ${update.comment}`,
            `Pattern match: ${pubMatch ? pubMatch[0] : 'none'}`
          );
        }

        return {
          ...update,
          pmid: pmid || null,
        };
      });
    },
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
