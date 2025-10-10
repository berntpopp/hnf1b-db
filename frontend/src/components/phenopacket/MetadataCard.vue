<!-- src/components/phenopacket/MetadataCard.vue -->
<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 py-2 bg-grey-lighten-4">
      <v-icon
        left
        color="grey-darken-2"
        size="small"
      >
        mdi-information-outline
      </v-icon>
      Metadata
    </v-card-title>
    <v-card-text class="pa-2">
      <v-list density="compact">
        <v-list-item v-if="metaData.created">
          <v-list-item-title class="font-weight-bold">
            Created
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ formatDate(metaData.created) }}
            <span
              v-if="metaData.createdBy"
              class="ml-2 text-grey"
            >
              by {{ metaData.createdBy }}
            </span>
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-if="metaData.phenopacketSchemaVersion">
          <v-list-item-title class="font-weight-bold">
            Schema Version
          </v-list-item-title>
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
                <v-icon
                  left
                  size="small"
                >
                  mdi-open-in-new
                </v-icon>
                {{ ref.id }}
              </v-chip>
              <span class="text-caption">{{ ref.description }}</span>
            </v-list-item>
          </v-list>
        </v-list-item>

        <v-divider
          v-if="metaData.updates && metaData.updates.length > 0"
          class="my-2"
        />

        <v-list-item v-if="filteredUpdates.length > 0">
          <v-list-item-title class="font-weight-bold mb-2">
            Data Updates ({{ filteredUpdates.length }})
          </v-list-item-title>
          <v-timeline
            density="compact"
            side="end"
          >
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
                <div
                  v-if="update.pmid"
                  class="text-body-2"
                >
                  Data from
                  <v-chip
                    :href="update.pmid.url"
                    target="_blank"
                    color="blue"
                    size="small"
                    variant="flat"
                    class="mx-1"
                  >
                    <v-icon
                      left
                      size="x-small"
                    >
                      mdi-open-in-new
                    </v-icon>
                    {{ update.pmid.id }}
                  </v-chip>
                </div>
                <div
                  v-else
                  class="text-body-2"
                >
                  {{ update.comment }}
                </div>
              </div>
            </v-timeline-item>
          </v-timeline>
        </v-list-item>

        <v-divider
          v-if="metaData.resources && metaData.resources.length > 0"
          class="my-2"
        />

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
              <v-chip
                color="green"
                size="small"
                variant="flat"
                class="mr-2"
              >
                {{ resource.namespacePrefix }}
              </v-chip>
              <span class="text-body-2">
                {{ resource.name }}
                <span
                  v-if="resource.version"
                  class="text-caption text-grey"
                >
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
        // Extract pub ID from comment (e.g., "Data from pub123" → "pub123")
        const pubMatch = update.comment?.match(/pub(\d+)/i);

        // If we have PMIDs, try to map based on order (pub123 → first PMID, pub156 → second PMID)
        let pmid = null;
        if (pubMatch && pmids.length > index) {
          pmid = pmids[index];
        }

        return {
          ...update,
          pmid: pmid,
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
  },
};
</script>
